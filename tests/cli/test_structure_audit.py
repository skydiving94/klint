"""The klint-structure command end to end, with the fake judge in place of the model."""

import asyncio
import json
import sys
from pathlib import Path
from typing import Any

import pytest
from injector import Binder

from klint.app.settings import AppSettings
from klint.catalog.code.language_neutral.extraction.file_metadata_base import (
    BaseFileMetadataExtractor,
)
from klint.catalog.code.language_neutral.units.file_metadata_unit import (
    AuditableFileMetadataUnit,
)
from klint.catalog.code.python.extraction.file_metadata_extractor import (
    PythonFileMetadataExtractor,
)
from klint.catalog.domain_neutral.extraction.dispatched_file import DispatchedFile
from klint.cli import klint_project_alias
from klint.cli.exit_code import ExitCode
from klint.cli.runner import AuditCommandApp, run_command_from_shell
from klint.cli.structure_audit import STRUCTURE_AUDIT_COMMAND
from klint.core.interfaces.judge import BaseJudge
from tests.support.builders import (
    DIR_RULE,
    FILE_RULE,
    MakeUnreadable,
    build_audit_command_app,
    make_settings,
    write_json,
    write_text,
)
from tests.support.fakes import FakeJudge, PickyJudge
from tests.support.paths import MOCK_PROJECT, SnapshotAsserter
from tests.support.stub_system_one_server import StubSystemOneServer

EXAMPLE_FILE = "examples/backend_data_and_security.py"


Capture = pytest.CaptureFixture[str]


def _structure_app(
    judge: BaseJudge, settings: AppSettings | None = None
) -> AuditCommandApp:
    return build_audit_command_app(STRUCTURE_AUDIT_COMMAND, judge, settings)


def _run(app: AuditCommandApp, *argv: str | Path) -> ExitCode:
    return asyncio.run(app.run([str(arg) for arg in argv]))


def _json_output(capsys: Capture) -> dict[str, Any]:
    output: dict[str, Any] = json.loads(capsys.readouterr().out)
    return output


@pytest.mark.usefixtures("in_repo_root")
def test_project_audit_json_matches_snapshot(
    tmp_path: Path,
    fake_judge: type[FakeJudge],
    capsys: Capture,
    assert_snapshot: SnapshotAsserter,
) -> None:
    pack = write_json(
        tmp_path / "rules.json",
        {
            "acyclic_packages": {
                **DIR_RULE,
                "instructions": "Do the packages import each other without cycles?",
            },
            "small_packages": {**DIR_RULE, "instructions": "Is each package small?"},
        },
    )
    judge = fake_judge(choices={"acyclic_packages": "fail"})
    app = _structure_app(judge, make_settings(built_in_rule_packs=[pack]))

    exit_code = _run(app, MOCK_PROJECT, "--json")

    assert exit_code == ExitCode.PROBLEMS_FOUND
    assert_snapshot("cli_structure_audit.json", capsys.readouterr().out)
    # One judge call per directory, the root and its three subdirectories,
    # each asked every rule.
    assert judge.asked_rule_ids() == [["acyclic_packages", "small_packages"]] * 4


@pytest.mark.usefixtures("in_repo_root")
def test_project_audit_rejects_a_file_target(
    fake_judge: type[FakeJudge], capsys: Capture
) -> None:
    judge = fake_judge()

    exit_code = _run(_structure_app(judge), EXAMPLE_FILE)

    assert exit_code == ExitCode.RUN_ERROR
    assert "must be a directory" in capsys.readouterr().err
    # The command stops before anything is audited.
    assert judge.requests == []


def test_target_under_a_folder_with_an_ignored_name_is_audited_in_full(
    tmp_path: Path, fake_judge: type[FakeJudge], capsys: Capture
) -> None:
    project = tmp_path / "build" / "project"
    write_text(project / "main.py", "x = 1\n")
    write_text(project / "pkg" / "a.py", "y = 2\n")
    judge = fake_judge(default="fail")

    _run(_structure_app(judge), project, "--json")

    output = _json_output(capsys)
    directories = [str(project), str(project / "pkg")]
    assert output["examined_directories"] == directories
    # The judge is asked about the directories listed as examined, and no others.
    reported_unit_ids = [issue["unit_id"] for issue in output["findings"]]
    assert list(dict.fromkeys(reported_unit_ids)) == directories
    assert len(judge.requests) == 2


def test_file_that_cannot_be_read_is_left_out_with_a_warning(
    tmp_path: Path,
    fake_judge: type[FakeJudge],
    capsys: Capture,
    make_unreadable: MakeUnreadable,
) -> None:
    package = tmp_path / "pkg"
    write_text(package / "a.py", "x = 1\n")
    locked = make_unreadable(write_text(package / "locked.py", "y = 2\n"))
    judge = fake_judge()

    exit_code = _run(_structure_app(judge), package, "--json")

    captured = capsys.readouterr()
    assert exit_code == ExitCode.NO_PROBLEMS
    assert json.loads(captured.out)["examined_directories"] == [str(package)]
    assert captured.err.splitlines() == [
        f"[klint-structure] Warning: File '{locked}' is left out: "
        "it cannot be read (Permission denied)"
    ]
    # The directory is described to the judge without that file.
    ((content, _rule_ids),) = judge.subject_to_asked_rule_ids().items()
    assert "a.py" in content
    assert "locked.py" not in content


class PythonExtractorBrokenOnB(PythonFileMetadataExtractor):
    """Fails on b.py, for a reason other than reading it; reads the rest as usual."""

    def extract_file(
        self, dispatched_file: DispatchedFile
    ) -> AuditableFileMetadataUnit:
        if dispatched_file.path.name == "b.py":
            raise RuntimeError("the extractor is broken on b.py")
        return super().extract_file(dispatched_file)


def use_the_extractor_broken_on_b_for_python(binder: Binder) -> None:
    binder.multibind(
        dict[str, BaseFileMetadataExtractor], to={"python": PythonExtractorBrokenOnB}
    )


def test_file_that_cannot_be_processed_is_left_out_with_a_warning(
    tmp_path: Path, fake_judge: type[FakeJudge], capsys: Capture
) -> None:
    package = tmp_path / "pkg"
    write_text(package / "a.py", "x = 1\n")
    broken = write_text(package / "b.py", "y = 2\n")
    judge = fake_judge()
    app = build_audit_command_app(
        STRUCTURE_AUDIT_COMMAND,
        judge,
        overrides=[use_the_extractor_broken_on_b_for_python],
    )

    exit_code = _run(app, package, "--json")

    captured = capsys.readouterr()
    assert exit_code == ExitCode.NO_PROBLEMS
    assert json.loads(captured.out)["examined_directories"] == [str(package)]
    assert captured.err.splitlines() == [
        f"[klint-structure] Warning: File '{broken}' is left out: "
        "it cannot be processed (the extractor is broken on b.py)"
    ]
    ((content, _rule_ids),) = judge.subject_to_asked_rule_ids().items()
    assert "a.py" in content
    assert "b.py" not in content


def test_directory_that_cannot_be_read_is_left_out_with_a_warning(
    tmp_path: Path,
    fake_judge: type[FakeJudge],
    capsys: Capture,
    make_unreadable: MakeUnreadable,
) -> None:
    repo = tmp_path / "repo"
    write_text(repo / "main.py", "x = 1\n")
    locked = make_unreadable(write_text(repo / "locked" / "a.py", "y = 2\n").parent)
    judge = fake_judge()

    exit_code = _run(_structure_app(judge), repo, "--json")

    captured = capsys.readouterr()
    assert exit_code == ExitCode.NO_PROBLEMS
    assert json.loads(captured.out)["examined_directories"] == [str(repo)]
    assert captured.err.splitlines() == [
        f"[klint-structure] Warning: Directory '{locked}' is left out: "
        "it cannot be read (Permission denied)"
    ]
    ((content, _rule_ids),) = judge.subject_to_asked_rule_ids().items()
    assert "locked" not in content


def test_binary_file_is_listed_by_name_only(
    tmp_path: Path, fake_judge: type[FakeJudge]
) -> None:
    package = tmp_path / "pkg"
    write_text(package / "a.py", "x = 1\n")
    (package / "logo.dat").write_bytes(b"\x00\x01\n\x02\n")
    judge = fake_judge()

    exit_code = _run(_structure_app(judge), package, "--json")

    assert exit_code == ExitCode.NO_PROBLEMS
    ((content, _rule_ids),) = judge.subject_to_asked_rule_ids().items()
    content_lines = content.splitlines()
    assert "    - logo.dat (binary)" in content_lines
    assert "    - a.py (lines=1)" in content_lines


def test_python_file_that_cannot_be_parsed_is_listed_with_a_warning(
    tmp_path: Path, fake_judge: type[FakeJudge], capsys: Capture
) -> None:
    package = tmp_path / "pkg"
    init_file = write_text(package / "__init__.py", '__all__ = ["Order"\n')
    write_text(package / "orders.py", "import json\n\n\nclass Order:\n    pass\n")
    judge = fake_judge()

    exit_code = _run(_structure_app(judge), package, "--json")

    captured = capsys.readouterr()
    assert exit_code == ExitCode.NO_PROBLEMS
    assert json.loads(captured.out)["examined_directories"] == [str(package)]
    assert captured.err.splitlines() == [
        f"[klint-structure] Warning: File '{init_file}' is listed by name and line "
        "count only: it cannot be parsed ('[' was never closed, line 1)"
    ]
    # The judge is told the file could not be parsed, not that it is empty.
    ((content, _rule_ids),) = judge.subject_to_asked_rule_ids().items()
    content_lines = content.splitlines()
    assert "    - __init__.py (lines=1; cannot be parsed)" in content_lines
    assert "    - orders.py (lines=5; imports=[json]; classes=[Order])" in content_lines


def test_package_description_marks_what_unparseable_files_leave_unknown(
    tmp_path: Path, fake_judge: type[FakeJudge], capsys: Capture
) -> None:
    package = tmp_path / "pkg"
    write_text(package / "__init__.py", '__all__ = ["Order"\n')
    write_text(package / "orders.py", "import json\n")
    write_text(package / "sub" / "__init__.py", "")
    write_text(package / "sub" / "b.py", "def (:\n")
    judge = fake_judge()

    exit_code = _run(_structure_app(judge), package, "--json")

    capsys.readouterr()
    assert exit_code == ExitCode.NO_PROBLEMS
    (root_content,) = [
        content
        for content in judge.subject_to_asked_rule_ids()
        if content.startswith(f"Target Directory Under Audit: {package} ")
    ]
    content_lines = root_content.splitlines()
    # The public API cannot be told from an __init__.py that cannot be parsed.
    assert "Package Public API Status: unknown (__init__.py cannot be parsed)" in (
        content_lines
    )
    # Every such file in the tree is named, so that the import lists and the
    # cycle check are not taken as complete.
    assert (
        "Files That Cannot Be Parsed in Tree: [__init__.py, sub/b.py] (their "
        "imports are unknown; the import lists and cycle check here leave them out)"
    ) in content_lines


def test_rules_for_python_are_asked_only_about_directories_holding_python(
    tmp_path: Path, fake_judge: type[FakeJudge], capsys: Capture
) -> None:
    python_pack = write_json(
        tmp_path / "python.json",
        {"applies_to": {"languages": ["python"]}, "rules": {"for_python": DIR_RULE}},
    )
    # A directory in no language is asked only the fallback packs: none here.
    settings = make_settings(built_in_rule_packs=[python_pack], fallback_rule_packs=[])
    repo = tmp_path / "repo"
    write_text(repo / "app" / "main.py", "x = 1\n")
    write_text(repo / "docs" / "intro.md", "# Intro\n")
    judge = fake_judge()

    _run(_structure_app(judge, settings), repo, "--json", "--all")

    output = _json_output(capsys)
    judged_unit_ids = {issue["unit_id"] for issue in output["findings"]}
    assert judged_unit_ids == {str(repo), str(repo / "app")}
    # The directory without Python is not sent to the judge at all, so it is
    # not listed as examined either.
    assert len(judge.requests) == 2
    assert output["examined_directories"] == [str(repo), str(repo / "app")]


def test_project_rules_path_variable_replaces_every_built_in_pack(
    tmp_path: Path, fake_judge: type[FakeJudge]
) -> None:
    override = write_json(tmp_path / "rules.json", {"only_rule": DIR_RULE})
    repo = tmp_path / "repo"
    write_text(repo / "app" / "main.py", "x = 1\n")
    write_text(repo / "docs" / "intro.md", "# Intro\n")
    judge = fake_judge()
    settings = make_settings(project_structure_rule_pack_override=override)

    _run(_structure_app(judge, settings), repo, "--json")

    # Every directory is asked, whatever language it is described in.
    assert judge.asked_rule_ids() == [["only_rule"]] * 3


def test_custom_rule_can_target_the_files_inside_a_directory(
    tmp_path: Path, fake_judge: type[FakeJudge], capsys: Capture
) -> None:
    python_file_rule = {
        **FILE_RULE,
        "target_unit_types": ["file_metadata"],
        "languages": ["python"],
    }
    custom = write_json(
        tmp_path / "custom.json",
        {"for_directory": DIR_RULE, "python_file": python_file_rule},
    )
    package = tmp_path / "pkg"
    for name in ("a.py", "b.java", "c.txt"):
        write_text(package / name, "x = 1\n")
    judge = fake_judge()
    # No rule but the custom ones.
    settings = make_settings(built_in_rule_packs=[], fallback_rule_packs=[])

    _run(_structure_app(judge, settings), package, "--json", "--rules", custom)

    contents_asked_the_file_rule = [
        content
        for content, rule_ids in judge.subject_to_asked_rule_ids().items()
        if rule_ids == {"python_file"}
    ]
    calls_with_the_directory_rule = [
        rule_ids for rule_ids in judge.asked_rule_ids() if "for_directory" in rule_ids
    ]
    # Only the Python file is asked the file rule, and the directory its own rule.
    assert contents_asked_the_file_rule == ["a.py (lines=1)"]
    assert len(calls_with_the_directory_rule) == 1
    assert len(judge.requests) == 2
    # Examined are the units the judge was asked about: here the directory
    # and the one file inside it that a rule targets.
    assert _json_output(capsys)["examined_directories"] == [
        str(package),
        str(package / "a.py"),
    ]


def test_directory_the_judge_fails_on_is_left_out_while_the_others_are_audited(
    tmp_path: Path, capsys: Capture
) -> None:
    repo = tmp_path / "repo"
    write_text(repo / "only_in_root.py", "x = 1\n")
    write_text(repo / "pkg" / "a.py", "y = 2\n")
    # What is sent for a directory names the files directly in it, so only the
    # content of the root holds this file name.
    judge = PickyJudge(refuses="only_in_root.py")

    exit_code = _run(_structure_app(judge), repo, "--json")

    captured = capsys.readouterr()
    assert exit_code == ExitCode.PROBLEMS_FOUND
    assert json.loads(captured.out)["examined_directories"] == [str(repo / "pkg")]
    assert f"Skipping {repo}: judge is down" in captured.err


def _run_main(
    monkeypatch: pytest.MonkeyPatch, settings: AppSettings, target: Path
) -> int:
    """Run the command as the shell would, but with the given settings."""
    monkeypatch.setattr(AppSettings, "from_env", lambda *_args: settings)
    monkeypatch.setattr(sys, "argv", ["klint-structure", str(target)])
    return asyncio.run(run_command_from_shell(STRUCTURE_AUDIT_COMMAND))


def test_unusable_language_to_file_extensions_file_stops_the_command(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: Capture
) -> None:
    broken = write_text(tmp_path / "language_to_file_extensions.json", "{not json")
    settings = make_settings(language_to_file_extensions_path=broken)

    exit_code = _run_main(monkeypatch, settings, tmp_path)

    captured = capsys.readouterr()
    assert exit_code == ExitCode.RUN_ERROR
    assert captured.out == ""
    assert captured.err.startswith(
        "[klint-structure] Error: Language-to-file-extensions file"
    )
    assert str(broken) in captured.err
    assert captured.err.count("\n") == 1


def test_old_command_name_runs_the_structure_audit_with_a_warning(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    shell_env: dict[str, str],
    capsys: Capture,
    system_one_server: StubSystemOneServer,
) -> None:
    package = write_text(tmp_path / "pkg" / "a.py", "x = 1\n").parent
    shell_env["KEV_MODE"] = "remote"
    shell_env["KEV_BASE_URL"] = system_one_server.base_url
    monkeypatch.setattr(sys, "argv", ["klint-project", str(package), "--json"])

    exit_code = klint_project_alias.cli_main()

    captured = capsys.readouterr()
    assert exit_code == ExitCode.NO_PROBLEMS
    assert captured.err.splitlines() == [
        "[klint-structure] Warning: 'klint-project' is deprecated and stops "
        "working in the next release; use 'klint-structure' instead"
    ]
    assert json.loads(captured.out)["examined_directories"] == [str(package)]
    assert len(system_one_server.received) == 1
