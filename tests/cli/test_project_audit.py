"""The klint-project command end to end, with the fake judge in place of the model."""

import asyncio
import json
import sys
from pathlib import Path
from typing import Any

import pytest

from src.app.settings import AppSettings
from src.app.wiring import create_project_audit_path
from src.cli.project_audit import PROJECT_AUDIT_COMMAND
from src.cli.runner import AuditCommandApp, run_command_from_shell
from src.core.interfaces.judge import BaseJudge
from tests.support.builders import (
    DIR_RULE,
    FILE_RULE,
    MakeUnreadable,
    make_settings,
    write_json,
    write_text,
)
from tests.support.fakes import FakeJudge, JudgeOverride, PickyJudge
from tests.support.paths import MOCK_PROJECT, SnapshotAsserter

EXAMPLE_FILE = "examples/backend_data_and_security.py"


Capture = pytest.CaptureFixture[str]


def _project_app(
    judge: BaseJudge, settings: AppSettings | None = None
) -> AuditCommandApp:
    audit_path = create_project_audit_path(
        settings or make_settings(), JudgeOverride(judge)
    )
    return AuditCommandApp(PROJECT_AUDIT_COMMAND, audit_path)


def _run(app: AuditCommandApp, *argv: str | Path) -> int:
    return asyncio.run(app.run([str(arg) for arg in argv]))


def _json_output(capsys: Capture) -> dict[str, Any]:
    output: dict[str, Any] = json.loads(capsys.readouterr().out)
    return output


@pytest.mark.usefixtures("in_repo_root")
def test_project_audit_json_matches_snapshot(
    fake_judge: type[FakeJudge], capsys: Capture, assert_snapshot: SnapshotAsserter
) -> None:
    judge = fake_judge(choices={"circular_package_dependencies": "fail"})

    exit_code = _run(_project_app(judge), MOCK_PROJECT, "--json")

    assert exit_code == 0
    assert_snapshot("cli_project_audit.json", capsys.readouterr().out)
    # One judge call per directory: the root and its three subdirectories.
    assert [len(rule_ids) for rule_ids in judge.asked_rule_ids()] == [18] * 4


@pytest.mark.usefixtures("in_repo_root")
def test_project_audit_rejects_a_file_target(
    fake_judge: type[FakeJudge], capsys: Capture
) -> None:
    judge = fake_judge()

    exit_code = _run(_project_app(judge), EXAMPLE_FILE)

    assert exit_code == 1
    assert "must be a directory" in capsys.readouterr().err
    # The command stops before anything is audited.
    assert judge.calls == []


def test_target_under_a_folder_with_an_ignored_name_is_audited_in_full(
    tmp_path: Path, fake_judge: type[FakeJudge], capsys: Capture
) -> None:
    project = tmp_path / "build" / "project"
    write_text(project / "main.py", "x = 1\n")
    write_text(project / "pkg" / "a.py", "y = 2\n")
    judge = fake_judge(default="fail")

    _run(_project_app(judge), project, "--json")

    output = _json_output(capsys)
    directories = [str(project), str(project / "pkg")]
    assert output["examined_directories"] == directories
    # The judge is asked about the directories listed as examined, and no others.
    reported_unit_ids = [issue["unit_id"] for issue in output["issues"]]
    assert list(dict.fromkeys(reported_unit_ids)) == directories
    assert len(judge.calls) == 2


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

    exit_code = _run(_project_app(judge), package, "--json")

    captured = capsys.readouterr()
    assert exit_code == 0
    assert json.loads(captured.out)["examined_directories"] == [str(package)]
    assert captured.err.splitlines() == [
        f"[klint-project] Warning: File '{locked}' is left out: "
        "it cannot be read (Permission denied)"
    ]
    # The directory is described to the judge without that file.
    ((content, _questions),) = judge.calls
    assert "a.py" in content
    assert "locked.py" not in content


def test_file_that_cannot_be_processed_is_left_out_with_a_warning(
    tmp_path: Path, fake_judge: type[FakeJudge], capsys: Capture
) -> None:
    package = tmp_path / "pkg"
    write_text(package / "a.py", "x = 1\n")
    # Nested too deeply for the Python parser, which gives up on the file.
    too_deep = write_text(package / "too_deep.py", "-" * 200_000 + "1\n")
    judge = fake_judge()

    exit_code = _run(_project_app(judge), package, "--json")

    captured = capsys.readouterr()
    assert exit_code == 0
    assert json.loads(captured.out)["examined_directories"] == [str(package)]
    (warning_line,) = captured.err.splitlines()
    assert warning_line.startswith(
        f"[klint-project] Warning: File '{too_deep}' is left out: "
        "it cannot be processed ("
    )
    ((content, _questions),) = judge.calls
    assert "a.py" in content
    assert "too_deep.py" not in content


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

    exit_code = _run(_project_app(judge), repo, "--json")

    captured = capsys.readouterr()
    assert exit_code == 0
    assert json.loads(captured.out)["examined_directories"] == [str(repo)]
    assert captured.err.splitlines() == [
        f"[klint-project] Warning: Directory '{locked}' is left out: "
        "it cannot be read (Permission denied)"
    ]
    ((content, _questions),) = judge.calls
    assert "locked" not in content


def test_binary_file_is_listed_by_name_only(
    tmp_path: Path, fake_judge: type[FakeJudge]
) -> None:
    package = tmp_path / "pkg"
    write_text(package / "a.py", "x = 1\n")
    (package / "logo.dat").write_bytes(b"\x00\x01\n\x02\n")
    judge = fake_judge()

    exit_code = _run(_project_app(judge), package, "--json")

    assert exit_code == 0
    ((content, _questions),) = judge.calls
    content_lines = content.splitlines()
    assert "    - logo.dat (binary)" in content_lines
    assert "    - a.py (lines=1)" in content_lines


def test_python_project_rules_are_asked_only_about_directories_holding_python(
    tmp_path: Path, fake_judge: type[FakeJudge], capsys: Capture
) -> None:
    repo = tmp_path / "repo"
    write_text(repo / "app" / "main.py", "x = 1\n")
    write_text(repo / "docs" / "intro.md", "# Intro\n")
    judge = fake_judge()

    _run(_project_app(judge), repo, "--json", "--all")

    judged_unit_ids = {issue["unit_id"] for issue in _json_output(capsys)["issues"]}
    assert judged_unit_ids == {str(repo), str(repo / "app")}
    # The directory without Python is not sent to the judge at all.
    assert len(judge.calls) == 2


def test_project_rules_path_variable_replaces_every_built_in_pack(
    tmp_path: Path, fake_judge: type[FakeJudge]
) -> None:
    override = write_json(tmp_path / "rules.json", {"only_rule": DIR_RULE})
    repo = tmp_path / "repo"
    write_text(repo / "app" / "main.py", "x = 1\n")
    write_text(repo / "docs" / "intro.md", "# Intro\n")
    judge = fake_judge()
    settings = make_settings(project_structure_rule_pack_override=override)

    _run(_project_app(judge, settings), repo, "--json")

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

    _run(_project_app(judge), package, "--json", "--rules", custom)

    contents_asked_the_file_rule = [
        content
        for content, questions in judge.calls
        if list(questions) == ["python_file"]
    ]
    calls_with_the_directory_rule = [
        questions for _, questions in judge.calls if "for_directory" in questions
    ]
    # Only the Python file is asked the file rule, and the directory its own rule.
    (file_content,) = contents_asked_the_file_rule
    assert "a.py" in file_content
    assert len(calls_with_the_directory_rule) == 1
    assert len(judge.calls) == 2
    assert _json_output(capsys)["examined_directories"] == [str(package)]


def test_directory_the_judge_fails_on_is_left_out_while_the_others_are_audited(
    tmp_path: Path, capsys: Capture
) -> None:
    repo = tmp_path / "repo"
    write_text(repo / "only_in_root.py", "x = 1\n")
    write_text(repo / "pkg" / "a.py", "y = 2\n")
    # What is sent for a directory names the files directly in it, so only the
    # content of the root holds this file name.
    judge = PickyJudge(refuses="only_in_root.py")

    exit_code = _run(_project_app(judge), repo, "--json")

    captured = capsys.readouterr()
    assert exit_code == 0
    assert json.loads(captured.out)["examined_directories"] == [str(repo / "pkg")]
    assert f"Skipping {repo}: judge is down" in captured.err


def _run_main(
    monkeypatch: pytest.MonkeyPatch, settings: AppSettings, target: Path
) -> int:
    """Run the command as the shell would, but with the given settings."""
    monkeypatch.setattr(AppSettings, "from_env", lambda *_args: settings)
    monkeypatch.setattr(sys, "argv", ["klint-project", str(target)])
    return asyncio.run(run_command_from_shell(PROJECT_AUDIT_COMMAND))


def test_unusable_language_to_file_extensions_file_stops_the_command(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: Capture
) -> None:
    broken = write_text(tmp_path / "language_to_file_extensions.json", "{not json")
    settings = make_settings(language_to_file_extensions_path=broken)

    exit_code = _run_main(monkeypatch, settings, tmp_path)

    captured = capsys.readouterr()
    assert exit_code == 1
    assert captured.out == ""
    assert captured.err.startswith(
        "[klint-project] Error: Language-to-file-extensions file"
    )
    assert str(broken) in captured.err
    assert captured.err.count("\n") == 1
