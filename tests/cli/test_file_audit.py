"""The klint command end to end, with the fake judge in place of the model."""

import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Any

import pytest
from injector import Binder

from klint.app.settings import AppSettings
from klint.catalog.code.language_neutral.practice_scale import PRACTICE_SCALE
from klint.catalog.domain_neutral.extraction.dispatched_file import DispatchedFile
from klint.cli.exit_code import ExitCode
from klint.cli.file_audit import FILE_AUDIT_COMMAND
from klint.cli.runner import AuditCommandApp, run_command_from_shell
from klint.core.interfaces.extractor import BaseUnitExtractor
from klint.core.interfaces.judge import BaseJudge
from klint.core.models.judge_exchange import JudgeQuestion
from klint.core.models.question_type import QuestionType
from klint.core.models.unit import AuditableUnit
from klint.infra.system_one.remote import RemoteSystemOneJudge
from tests.support.builders import (
    DIR_RULE,
    FILE_RULE,
    MakeUnreadable,
    build_audit_command_app,
    make_settings,
    write_json,
    write_text,
)
from tests.support.fakes import CountingJudge, FakeJudge, PickyJudge
from tests.support.paths import SnapshotAsserter
from tests.support.stub_system_one_server import StubSystemOneServer

EXAMPLE_FILE = "examples/backend_data_and_security.py"


Capture = pytest.CaptureFixture[str]


def _file_app(judge: BaseJudge, settings: AppSettings | None = None) -> AuditCommandApp:
    return build_audit_command_app(FILE_AUDIT_COMMAND, judge, settings)


def _run(app: AuditCommandApp, *argv: str | Path) -> ExitCode:
    return asyncio.run(app.run([str(arg) for arg in argv]))


def _json_output(capsys: Capture) -> dict[str, Any]:
    output: dict[str, Any] = json.loads(capsys.readouterr().out)
    return output


@pytest.mark.usefixtures("in_repo_root")
def test_file_audit_json_matches_snapshot(
    tmp_path: Path,
    fake_judge: type[FakeJudge],
    capsys: Capture,
    assert_snapshot: SnapshotAsserter,
) -> None:
    pack = write_json(
        tmp_path / "rules.json",
        {
            "clear_names": {**FILE_RULE, "instructions": "Are the names clear?"},
            "short_functions": {**FILE_RULE, "instructions": "Are functions short?"},
            "typed_functions": {**FILE_RULE, "instructions": "Are functions typed?"},
        },
    )
    judge = fake_judge(choices={"clear_names": "fail", "short_functions": "fail"})
    app = _file_app(judge, make_settings(built_in_rule_packs=[pack]))

    exit_code = _run(app, EXAMPLE_FILE, "--json")

    assert exit_code == ExitCode.PROBLEMS_FOUND
    assert_snapshot("cli_file_audit.json", capsys.readouterr().out)


def test_all_answers_flag_reports_every_answer(
    tmp_path: Path, fake_judge: type[FakeJudge], capsys: Capture
) -> None:
    pack = write_json(
        tmp_path / "rules.json",
        {"a_rule": FILE_RULE, "b_rule": FILE_RULE, "c_rule": FILE_RULE},
    )
    target = write_text(tmp_path / "a.py", "x = 1\n")
    judge = fake_judge(choices={"b_rule": "fail"})
    app = _file_app(judge, make_settings(built_in_rule_packs=[pack]))

    _run(app, target, "--json")
    failed = [(i["rule_id"], i["answer"]) for i in _json_output(capsys)["findings"]]
    _run(app, target, "--json", "--all-answers")
    judged = [(i["rule_id"], i["answer"]) for i in _json_output(capsys)["findings"]]

    assert failed == [("b_rule", "Fail")]
    # Every rule that was asked is reported, and only the one failed.
    assert judged == [("b_rule", "Fail"), ("a_rule", "Pass"), ("c_rule", "Pass")]


def test_min_confidence_hides_low_confidence_findings(
    tmp_path: Path, fake_judge: type[FakeJudge], capsys: Capture
) -> None:
    target = write_text(tmp_path / "a.py", "x = 1\n")
    app = _file_app(fake_judge(default="fail", confidence=0.4))

    _run(app, target, "--json", "--min-confidence", "0.5")
    above_confidence = _json_output(capsys)
    _run(app, target, "--json", "--min-confidence", "0.3")
    below_confidence = _json_output(capsys)

    # A problem below the least confidence does not count in the roll-up either.
    assert above_confidence == {
        "examined_files": [str(target)],
        "unit_id_to_roll_up_status": {str(target): "no_problem"},
        "findings": [],
    }
    assert below_confidence["findings"]
    assert below_confidence["unit_id_to_roll_up_status"] == {str(target): "own_problem"}


def test_pack_for_some_languages_is_asked_only_about_files_in_them(
    tmp_path: Path, fake_judge: type[FakeJudge]
) -> None:
    shared = write_json(tmp_path / "shared.json", {"for_every_file": FILE_RULE})
    web = write_json(
        tmp_path / "web.json",
        {
            "applies_to": {"languages": ["typescript", "javascript"]},
            "rules": {"for_web": FILE_RULE},
        },
    )
    settings = make_settings(
        built_in_rule_packs=[shared, web], fallback_rule_packs=[shared]
    )
    sources = tmp_path / "sources"
    # Each file holds its own name, which tells the requests to the judge apart.
    for name in ("a.py", "b.tsx", "c.js", "notes.txt"):
        write_text(sources / name, name)
    judge = fake_judge()

    _run(_file_app(judge, settings), sources, "--json")

    file_name_to_asked_rule_ids = judge.subject_to_asked_rule_ids()
    # A rule in a pack that names no language is asked about every file.
    assert file_name_to_asked_rule_ids == {
        "a.py": {"for_every_file"},
        "b.tsx": {"for_every_file", "for_web"},
        "c.js": {"for_every_file", "for_web"},
        "notes.txt": {"for_every_file"},
    }


def test_custom_rule_is_asked_only_about_the_unit_type_and_language_it_names(
    tmp_path: Path, fake_judge: type[FakeJudge]
) -> None:
    custom = write_json(
        tmp_path / "custom.json",
        {
            "any_language": FILE_RULE,
            "python_only": {**FILE_RULE, "languages": ["python"]},
            "for_directory": DIR_RULE,
        },
    )
    sources = tmp_path / "sources"
    # Each file holds its own name, which tells the requests to the judge apart.
    for name in ("a.py", "a.go", "notes.txt"):
        write_text(sources / name, name)
    judge = fake_judge()

    _run(_file_app(judge), sources, "--json", "--rules", custom)

    custom_rule_ids = {"any_language", "python_only", "for_directory"}
    file_name_to_asked_rule_ids = {
        content: custom_rule_ids & rule_ids
        for content, rule_ids in judge.subject_to_asked_rule_ids().items()
    }
    # A file in another language, or in none that is known, is not asked the
    # Python rule. No file is asked the rule for directories.
    assert file_name_to_asked_rule_ids == {
        "a.py": {"any_language", "python_only"},
        "a.go": {"any_language"},
        "notes.txt": {"any_language"},
    }


def test_file_of_unidentified_language_is_asked_only_the_fallback_packs(
    tmp_path: Path, fake_judge: type[FakeJudge]
) -> None:
    code = write_json(tmp_path / "code.json", {"for_code": FILE_RULE})
    fallback = write_json(tmp_path / "prose.json", {"for_prose": FILE_RULE})
    settings = make_settings(built_in_rule_packs=[code], fallback_rule_packs=[fallback])
    sources = tmp_path / "sources"
    # Each file holds its own name, which tells the requests to the judge apart.
    for name in ("a.py", "notes.txt"):
        write_text(sources / name, name)
    judge = fake_judge()

    _run(_file_app(judge, settings), sources)

    file_name_to_asked_rule_ids = judge.subject_to_asked_rule_ids()
    assert file_name_to_asked_rule_ids == {
        "a.py": {"for_code"},
        "notes.txt": {"for_prose"},
    }


def test_tree_of_python_files_loads_no_pack_made_for_another_language(
    tmp_path: Path, fake_judge: type[FakeJudge], capsys: Capture
) -> None:
    python_pack = write_json(
        tmp_path / "python.json",
        {"applies_to": {"languages": ["python"]}, "rules": {"for_python": FILE_RULE}},
    )
    # A pack for TypeScript whose rule is warned about as soon as it is read.
    typescript_pack = write_json(
        tmp_path / "typescript.json",
        {
            "applies_to": {"languages": ["typescript"]},
            "rules": {"typo": {**FILE_RULE, "langauges": ["typescript"]}},
        },
    )
    settings = make_settings(built_in_rule_packs=[python_pack, typescript_pack])
    sources = tmp_path / "sources"
    write_text(sources / "a.py", "x = 1\n")
    write_text(sources / "pkg" / "b.py", "y = 2\n")
    judge = fake_judge()

    _run(_file_app(judge, settings), sources, "--json")

    assert capsys.readouterr().err == ""
    assert judge.asked_rule_ids() == [["for_python"]] * 2

    write_text(sources / "c.ts", "let z = 3;\n")
    _run(_file_app(fake_judge(), settings), sources, "--json")

    assert "Rule 'typo'" in capsys.readouterr().err


def test_rules_path_variable_replaces_every_built_in_pack(
    tmp_path: Path, fake_judge: type[FakeJudge]
) -> None:
    override = write_json(tmp_path / "rules.json", {"only_rule": FILE_RULE})
    sources = tmp_path / "sources"
    for name in ("a.py", "b.tsx", "notes.txt"):
        write_text(sources / name, name)
    judge = fake_judge()
    settings = make_settings(file_contents_rule_pack_override=override)

    _run(_file_app(judge, settings), sources, "--json")

    # Whatever the language of the file, or none.
    assert judge.asked_rule_ids() == [["only_rule"]] * 3


def test_directory_audit_skips_ignored_and_binary_files(
    tmp_path: Path, fake_judge: type[FakeJudge], capsys: Capture
) -> None:
    (tmp_path / "node_modules").mkdir()
    for name in ("b.tsx", "a.py", "logo.png", ".env", ".git", "node_modules/dep.js"):
        (tmp_path / name).write_text("x\n", encoding="utf-8")
    (tmp_path / "blob.dat").write_bytes(b"\x00\x01")
    judge = fake_judge()

    _run(_file_app(judge), tmp_path, "--json")

    examined = _json_output(capsys)["examined_files"]
    assert examined == [str(tmp_path / "a.py"), str(tmp_path / "b.tsx")]
    assert len(judge.requests) == 2


def test_file_that_cannot_be_read_is_left_out_with_a_warning(
    tmp_path: Path,
    fake_judge: type[FakeJudge],
    capsys: Capture,
    make_unreadable: MakeUnreadable,
) -> None:
    write_text(tmp_path / "a.py", "x = 1\n")
    locked = make_unreadable(write_text(tmp_path / "locked.py", "y = 2\n"))
    judge = fake_judge()

    exit_code = _run(_file_app(judge), tmp_path, "--json")

    captured = capsys.readouterr()
    assert exit_code == ExitCode.NO_PROBLEMS
    assert json.loads(captured.out)["examined_files"] == [str(tmp_path / "a.py")]
    assert captured.err.splitlines() == [
        f"[klint] Warning: File '{locked}' is left out: "
        "it cannot be read (Permission denied)"
    ]
    assert len(judge.requests) == 1


def test_directory_that_cannot_be_read_is_left_out_with_a_warning(
    tmp_path: Path,
    fake_judge: type[FakeJudge],
    capsys: Capture,
    make_unreadable: MakeUnreadable,
) -> None:
    write_text(tmp_path / "a.py", "x = 1\n")
    locked = make_unreadable(write_text(tmp_path / "locked" / "b.py", "y = 2\n").parent)
    judge = fake_judge()

    exit_code = _run(_file_app(judge), tmp_path, "--json")

    captured = capsys.readouterr()
    assert exit_code == ExitCode.NO_PROBLEMS
    assert json.loads(captured.out)["examined_files"] == [str(tmp_path / "a.py")]
    assert captured.err.splitlines() == [
        f"[klint] Warning: Directory '{locked}' is left out: "
        "it cannot be read (Permission denied)"
    ]
    assert len(judge.requests) == 1


class BrokenExtractor(BaseUnitExtractor[DispatchedFile]):
    """Fails on every file, for a reason other than reading it."""

    async def extract(self, audit_input: DispatchedFile) -> list[AuditableUnit]:
        raise RuntimeError(f"the extractor is broken on {audit_input.path.name}")


def use_the_broken_extractor_for_python(binder: Binder) -> None:
    binder.multibind(
        dict[str, BaseUnitExtractor[DispatchedFile]], to={"python": BrokenExtractor}
    )


def test_file_an_extractor_fails_on_is_left_out_with_a_warning(
    tmp_path: Path, fake_judge: type[FakeJudge], capsys: Capture
) -> None:
    write_text(tmp_path / "a.go", "package a\n")
    broken = write_text(tmp_path / "b.py", "x = 1\n")
    judge = fake_judge()
    app = build_audit_command_app(
        FILE_AUDIT_COMMAND, judge, overrides=[use_the_broken_extractor_for_python]
    )

    exit_code = _run(app, tmp_path, "--json")

    captured = capsys.readouterr()
    assert exit_code == ExitCode.NO_PROBLEMS
    # The Go file is read by the language-neutral extractor, as before.
    assert json.loads(captured.out)["examined_files"] == [str(tmp_path / "a.go")]
    assert captured.err.splitlines() == [
        f"[klint] Warning: File '{broken}' is left out: "
        "it cannot be processed (the extractor is broken on b.py)"
    ]
    assert len(judge.requests) == 1


def test_target_that_is_neither_a_file_nor_a_directory_holds_nothing_to_audit(
    tmp_path: Path, fake_judge: type[FakeJudge], capsys: Capture
) -> None:
    named_pipe = tmp_path / "pipe"
    os.mkfifo(named_pipe)
    judge = fake_judge()

    exit_code = _run(_file_app(judge), named_pipe, "--json")

    assert exit_code == ExitCode.NO_PROBLEMS
    assert _json_output(capsys) == {
        "examined_files": [],
        "unit_id_to_roll_up_status": {},
        "findings": [],
    }
    assert judge.requests == []


def test_target_under_a_folder_with_an_ignored_name_is_audited_in_full(
    tmp_path: Path, fake_judge: type[FakeJudge], capsys: Capture
) -> None:
    target = tmp_path / "build" / "project"
    write_text(target / "a.py", "x = 1\n")
    write_text(target / "pkg" / "b.py", "y = 2\n")
    judge = fake_judge()

    _run(_file_app(judge), target, "--json")

    examined = _json_output(capsys)["examined_files"]
    assert examined == [str(target / "a.py"), str(target / "pkg" / "b.py")]
    assert len(judge.requests) == 2


def test_rules_flag_adds_custom_rules_to_the_defaults(
    tmp_path: Path, fake_judge: type[FakeJudge], capsys: Capture
) -> None:
    pack = write_json(tmp_path / "pack.json", {"pack_rule": FILE_RULE})
    custom = write_json(tmp_path / "custom.json", {"house_rule": FILE_RULE})
    target = write_text(tmp_path / "a.py", "x = 1\n")
    judge = fake_judge(choices={"house_rule": "fail"})
    app = _file_app(judge, make_settings(built_in_rule_packs=[pack]))

    _run(app, target, "--json", "--rules", custom)

    assert [i["rule_id"] for i in _json_output(capsys)["findings"]] == ["house_rule"]
    # The rules of the packs are still asked.
    assert judge.asked_rule_ids() == [["house_rule", "pack_rule"]]


def test_judge_is_sent_the_file_content_and_a_rule_as_a_question(
    tmp_path: Path, fake_judge: type[FakeJudge]
) -> None:
    custom = write_json(tmp_path / "custom.json", {"house_rule": FILE_RULE})
    target = write_text(tmp_path / "a.py", "x = 1\n")
    judge = fake_judge()

    _run(_file_app(judge), target, "--json", "--rules", custom)

    (request,) = judge.requests
    assert request.subject == "x = 1\n"
    (house_rule_question,) = [
        question
        for question in request.questions
        if question.question_id == "house_rule"
    ]
    assert house_rule_question == JudgeQuestion(
        question_id="house_rule",
        question_type=QuestionType.CHOICE,
        question=FILE_RULE["instructions"],
        choice_key_to_criterion=PRACTICE_SCALE.map_choice_key_to_criterion(),
    )


def test_rule_the_judge_does_not_answer_is_left_out_of_the_report(
    tmp_path: Path, fake_judge: type[FakeJudge], capsys: Capture
) -> None:
    custom = write_json(
        tmp_path / "custom.json", {"answered": FILE_RULE, "unanswered": FILE_RULE}
    )
    target = write_text(tmp_path / "a.py", "x = 1\n")
    judge = fake_judge(choices={"unanswered": None})

    _run(_file_app(judge), target, "--json", "--all-answers", "--rules", custom)

    reported_rule_ids = {issue["rule_id"] for issue in _json_output(capsys)["findings"]}
    assert "answered" in reported_rule_ids
    assert "unanswered" not in reported_rule_ids


def test_missing_target_or_rules_file_exits_with_an_error(
    tmp_path: Path, fake_judge: type[FakeJudge], capsys: Capture
) -> None:
    judge = fake_judge()
    app = _file_app(judge)
    target = tmp_path / "a.py"
    target.write_text("x = 1\n", encoding="utf-8")

    assert _run(app, tmp_path / "absent.py") == ExitCode.RUN_ERROR
    assert "Audit target does not exist" in capsys.readouterr().err
    assert _run(app, target, "--rules", tmp_path / "absent.json") == ExitCode.RUN_ERROR
    assert "Rules file does not exist" in capsys.readouterr().err
    # The command stops before anything is audited.
    assert judge.requests == []


def test_malformed_custom_rule_stops_the_command_naming_the_rule_and_the_file(
    tmp_path: Path, fake_judge: type[FakeJudge], capsys: Capture
) -> None:
    custom = write_json(
        tmp_path / "custom.json",
        {"house_rule": {**FILE_RULE, "target_unit_types": "file"}},
    )
    target = write_text(tmp_path / "a.py", "x = 1\n")
    judge = fake_judge()

    exit_code = _run(_file_app(judge), target, "--rules", custom)

    (error_line,) = capsys.readouterr().err.splitlines()
    assert exit_code == ExitCode.RUN_ERROR
    assert error_line == (
        "[klint] Error: Rule 'house_rule' has invalid target_unit_types 'file' "
        f"in '{custom.resolve()}'; expected a list of strings"
    )
    assert judge.requests == []


def test_rules_file_that_cannot_be_read_exits_with_an_error(
    tmp_path: Path,
    fake_judge: type[FakeJudge],
    capsys: Capture,
    make_unreadable: MakeUnreadable,
) -> None:
    judge = fake_judge()
    target = write_text(tmp_path / "a.py", "x = 1\n")
    rules = make_unreadable(write_json(tmp_path / "rules.json", {}))

    exit_code = _run(_file_app(judge), target, "--rules", rules)

    (error_line,) = capsys.readouterr().err.splitlines()
    assert exit_code == ExitCode.RUN_ERROR
    assert error_line.startswith("[klint] Error: ")
    assert judge.requests == []


@pytest.mark.parametrize(
    ("content", "reason"),
    [("{not json", "is not valid JSON"), (None, "does not exist")],
)
def test_unusable_language_to_file_extensions_file_stops_the_command(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: Capture,
    content: str | None,
    reason: str,
) -> None:
    data_file = tmp_path / "language_to_file_extensions.json"
    if content is not None:
        write_text(data_file, content)
    target = write_text(tmp_path / "a.py", "x = 1\n")
    settings = make_settings(language_to_file_extensions_path=data_file)
    monkeypatch.setattr(AppSettings, "from_env", lambda *_args: settings)
    monkeypatch.setattr(sys, "argv", ["klint", str(target)])

    exit_code = asyncio.run(run_command_from_shell(FILE_AUDIT_COMMAND))

    captured = capsys.readouterr()
    assert exit_code == ExitCode.RUN_ERROR
    assert captured.out == ""
    assert captured.err.startswith("[klint] Error: Language-to-file-extensions file")
    assert reason in captured.err
    assert str(data_file) in captured.err
    assert captured.err.count("\n") == 1


def test_problem_in_one_rule_is_printed_as_a_warning_and_the_audit_goes_on(
    tmp_path: Path, fake_judge: type[FakeJudge], capsys: Capture
) -> None:
    custom = write_json(
        tmp_path / "custom.json", {"typo": {**FILE_RULE, "languages": ["pyhton"]}}
    )
    target = write_text(tmp_path / "a.py", "x = 1\n")

    exit_code = _run(_file_app(fake_judge()), target, "--json", "--rules", custom)

    captured = capsys.readouterr()
    assert exit_code == ExitCode.NO_PROBLEMS
    assert json.loads(captured.out)["examined_files"] == [str(target)]
    (warning_line,) = captured.err.splitlines()
    assert warning_line.startswith("[klint] Warning: Rule 'typo'")
    assert "unknown languages ['pyhton']" in warning_line


def test_file_the_judge_server_fails_on_is_skipped_and_stops_the_run(
    tmp_path: Path, capsys: Capture, system_one_server: StubSystemOneServer
) -> None:
    target = tmp_path / "a.py"
    target.write_text("x = 1\n", encoding="utf-8")
    system_one_server.response_status = 503
    judge = RemoteSystemOneJudge(model_name="fake", base_url=system_one_server.base_url)

    exit_code = _run(_file_app(judge), target, "--json")

    captured = capsys.readouterr()
    # The only file could not be audited, so nothing was checked.
    assert exit_code == ExitCode.RUN_ERROR
    assert captured.out == ""
    assert captured.err.splitlines() == [
        f"[klint] Skipping {target}: HTTP Error 503: Service Unavailable",
        "[klint] Error: None of the 1 unit(s) to audit could be audited",
    ]


def test_file_the_judge_fails_on_is_left_out_while_the_others_are_audited(
    tmp_path: Path, capsys: Capture
) -> None:
    write_text(tmp_path / "a.py", "x = 1\n")
    write_text(tmp_path / "b.py", "poison\n")
    write_text(tmp_path / "c.py", "y = 2\n")

    exit_code = _run(_file_app(PickyJudge(refuses="poison")), tmp_path, "--json")

    captured = capsys.readouterr()
    output = json.loads(captured.out)
    audited = [str(tmp_path / "a.py"), str(tmp_path / "c.py")]
    assert exit_code == ExitCode.PROBLEMS_FOUND
    assert output["examined_files"] == audited
    # Findings come out one file at a time, in the order of the files.
    reported_unit_ids = [issue["unit_id"] for issue in output["findings"]]
    assert list(dict.fromkeys(reported_unit_ids)) == audited
    assert f"Skipping {tmp_path / 'b.py'}: judge is down" in captured.err


def test_no_more_than_the_limit_is_audited_at_once(tmp_path: Path) -> None:
    for index in range(20):
        write_text(tmp_path / f"m{index:02}.py", "x = 1\n")
    judge = CountingJudge()

    _run(_file_app(judge), tmp_path, "--json")

    assert 1 < judge.most_at_once <= 8


def test_terminal_report_shows_findings_and_summary(
    tmp_path: Path, fake_judge: type[FakeJudge], capsys: Capture
) -> None:
    pack = write_json(
        tmp_path / "rules.json", {"house_rule": FILE_RULE, "other_rule": FILE_RULE}
    )
    target = write_text(tmp_path / "a.py", "x = 1\ny = 2\nz = 3\n")
    settings = make_settings(built_in_rule_packs=[pack])

    _run(_file_app(fake_judge(), settings), target)
    assert "No architectural or semantic issues found." in capsys.readouterr().out

    judge = fake_judge(choices={"house_rule": "fail"})
    _run(_file_app(judge, settings), target)

    report = capsys.readouterr().out
    assert "klint Audit Report" in report
    assert "[FAIL]" in report
    assert "house_rule" in report
    assert "(lines 1-3)" in report
    assert "1 files scanned | 1 units audited" in report
    assert "1 failure(s)" in report


def test_terminal_report_counts_the_files_scanned_and_the_units_audited(
    tmp_path: Path, fake_judge: type[FakeJudge], capsys: Capture
) -> None:
    write_text(tmp_path / "a.py", "x = 1\n")
    write_text(tmp_path / "pkg" / "b.py", "y = 2\n")
    # Scanned, but a binary file gives no unit to audit.
    (tmp_path / "blob.dat").write_bytes(b"\x00\x01")

    _run(_file_app(fake_judge()), tmp_path)

    report = capsys.readouterr().out
    assert "(3 files scanned, 2 units audited)" in report
