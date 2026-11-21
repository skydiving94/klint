"""The klint-structure command on a unified diff, with --diff-from."""

import asyncio
import io
import json
import sys
from pathlib import Path
from typing import Any

import pytest

from klint.cli import STRUCTURE_AUDIT_COMMAND, ExitCode
from tests.support.builders import (
    DIR_RULE,
    build_audit_command_app,
    list_lines_before_judge_usage,
    make_settings,
    write_json,
)
from tests.support.fakes import FakeJudge
from tests.support.git_repository import (
    create_repository,
    isolate_git,
    run_git,
    write_files,
)

Capture = pytest.CaptureFixture[str]

PROJECT_FILES = {
    "main.py": "from app.core import engine\n",
    "app/__init__.py": "",
    "app/core/__init__.py": "",
    "app/core/engine.py": "def run() -> None:\n    pass\n",
    "app/core/rules.py": "RULES = []\n",
    "app/web/__init__.py": "",
    "app/web/views.py": "def index() -> str:\n    return 'hi'\n",
    "node_modules/lib/index.js": "export const x = 1;\n",
}
EVERY_DIRECTORY = [".", "app", "app/core", "app/web"]


@pytest.fixture
def project(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    """Return a committed project with two packages, as the cwd."""
    isolate_git(monkeypatch, tmp_path)
    repository = create_repository(tmp_path / "shop", PROJECT_FILES)
    monkeypatch.chdir(repository)
    return repository


def run_structure_command(judge: FakeJudge, tmp_path: Path, *options: str) -> ExitCode:
    pack = write_json(tmp_path / "rules.json", {"tidy_directory": DIR_RULE})
    settings = make_settings(built_in_rule_packs=[pack], fallback_rule_packs=[pack])
    app = build_audit_command_app(STRUCTURE_AUDIT_COMMAND, judge, settings)
    return asyncio.run(app.run(list(options)))


def stage_and_pipe(monkeypatch: pytest.MonkeyPatch, repository: Path) -> str:
    """Stage every change, and make its diff what the command reads on stdin."""
    run_git(repository, "add", "--all")
    diff_text = run_git(repository, "diff", "--cached")
    stdin = io.TextIOWrapper(io.BytesIO(diff_text.encode("utf-8")), encoding="utf-8")
    monkeypatch.setattr(sys, "stdin", stdin)
    return diff_text


def audit_diff_as_json(
    judge: FakeJudge, tmp_path: Path, capsys: Capture
) -> dict[str, Any]:
    exit_code = run_structure_command(judge, tmp_path, "--diff-from", "-", "--json")
    assert exit_code == ExitCode.NO_PROBLEMS
    output: dict[str, Any] = json.loads(capsys.readouterr().out)
    return output


def test_a_change_deep_in_a_package_audits_its_package_and_parents(
    project: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: Capture
) -> None:
    write_files(project, {"app/core/engine.py": "def run() -> int:\n    return 1\n"})
    stage_and_pipe(monkeypatch, project)
    judge = FakeJudge()

    output = audit_diff_as_json(judge, tmp_path, capsys)

    assert output["diff_change"] == {
        "files": ["app/core/engine.py"],
        "deleted_files": [],
        "unit_count": output["diff_change"]["unit_count"],
        "selected_unit_count": 3,
        "audited_directories": [".", "app", "app/core"],
    }
    assert output["examined_directories"] == [".", "app", "app/core"]
    assert len(judge.requests) == 3


def test_each_audited_directory_is_shown_all_of_its_files(
    project: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: Capture
) -> None:
    write_files(project, {"app/core/engine.py": "def run() -> int:\n    return 1\n"})
    stage_and_pipe(monkeypatch, project)
    full_judge = FakeJudge()
    run_structure_command(full_judge, tmp_path, ".", "--json")
    capsys.readouterr()
    judge = FakeJudge()

    audit_diff_as_json(judge, tmp_path, capsys)

    # Each directory is asked about exactly as a full audit asks about it,
    # unchanged files and subpackages included.
    assert len(judge.requests) == 3
    full_subjects = [request.subject for request in full_judge.requests]
    subjects = [request.subject for request in judge.requests]
    assert all(subject in full_subjects for subject in subjects)
    assert any("rules.py" in subject for subject in subjects)
    assert any("web" in subject for subject in subjects)


def test_a_change_at_the_root_audits_the_root_alone(
    project: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: Capture
) -> None:
    write_files(project, {"main.py": "print('shop')\n"})
    stage_and_pipe(monkeypatch, project)
    judge = FakeJudge()

    output = audit_diff_as_json(judge, tmp_path, capsys)

    assert output["diff_change"]["audited_directories"] == ["."]
    assert output["examined_directories"] == ["."]
    assert len(judge.requests) == 1


def test_a_rename_across_packages_audits_both_packages(
    project: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: Capture
) -> None:
    run_git(project, "mv", "app/core/rules.py", "app/web/rules.py")
    stage_and_pipe(monkeypatch, project)
    judge = FakeJudge()

    output = audit_diff_as_json(judge, tmp_path, capsys)

    assert output["diff_change"]["files"] == ["app/web/rules.py"]
    assert output["diff_change"]["audited_directories"] == EVERY_DIRECTORY
    assert len(judge.requests) == len(EVERY_DIRECTORY)


def test_a_deleted_directory_audits_its_parent(
    project: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: Capture
) -> None:
    run_git(project, "rm", "--quiet", "-r", "app/web")
    stage_and_pipe(monkeypatch, project)
    judge = FakeJudge()

    output = audit_diff_as_json(judge, tmp_path, capsys)

    assert output["diff_change"]["files"] == []
    assert output["diff_change"]["deleted_files"] == [
        "app/web/__init__.py",
        "app/web/views.py",
    ]
    assert output["diff_change"]["audited_directories"] == [".", "app"]
    assert output["examined_directories"] == [".", "app"]
    assert len(judge.requests) == 2


def test_the_report_says_how_many_directories_the_change_selected(
    project: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: Capture
) -> None:
    write_files(project, {"app/web/views.py": "def index() -> str:\n    return ''\n"})
    run_git(project, "rm", "--quiet", "app/core/rules.py")
    stage_and_pipe(monkeypatch, project)

    exit_code = run_structure_command(FakeJudge(), tmp_path, "--diff-from", "-")

    assert exit_code == ExitCode.NO_PROBLEMS
    assert list_lines_before_judge_usage(capsys.readouterr().err) == [
        "[klint-structure] Change in the diff: 1 file and 1 deleted file, "
        "4 of 4 directories selected"
    ]


def test_an_empty_diff_audits_nothing(
    project: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: Capture
) -> None:
    assert stage_and_pipe(monkeypatch, project) == ""
    judge = FakeJudge()

    exit_code = run_structure_command(judge, tmp_path, "--diff-from", "-")

    assert exit_code == ExitCode.NO_PROBLEMS
    assert judge.requests == []
    assert "[klint-structure] No change in the diff to audit" in (
        capsys.readouterr().err
    )


def test_a_change_only_to_ignored_files_audits_nothing(
    project: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: Capture
) -> None:
    write_files(
        project,
        {
            "node_modules/lib/index.js": "export const x = 2;\n",
            "app/logo.png": b"\x89PNG\r\n\x1a\n\x00\x00",
        },
    )
    run_git(project, "add", "--force", "--all")
    stage_and_pipe(monkeypatch, project)
    judge = FakeJudge()

    exit_code = run_structure_command(judge, tmp_path, "--diff-from", "-")

    assert exit_code == ExitCode.NO_PROBLEMS
    assert judge.requests == []
    assert list_lines_before_judge_usage(capsys.readouterr().err) == [
        "[klint-structure] Change in the diff: 2 files, in no directory the "
        "audit covers"
    ]


def test_a_deleted_ignored_directory_audits_nothing(
    project: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: Capture
) -> None:
    run_git(project, "rm", "--quiet", "-r", "node_modules")
    stage_and_pipe(monkeypatch, project)
    judge = FakeJudge()

    output = audit_diff_as_json(judge, tmp_path, capsys)

    assert output["diff_change"]["audited_directories"] == []
    assert judge.requests == []


def test_a_file_that_does_not_match_the_diff_is_refused(
    project: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: Capture
) -> None:
    write_files(project, {"main.py": "print('shop')\n"})
    stage_and_pipe(monkeypatch, project)
    write_files(project, {"main.py": "print('edited again')\n"})
    judge = FakeJudge()

    exit_code = run_structure_command(judge, tmp_path, "--diff-from", "-")

    assert exit_code == ExitCode.RUN_ERROR
    assert judge.requests == []
    assert "does not match the files on disk" in capsys.readouterr().err


@pytest.mark.parametrize(
    "options",
    [
        ["--diff-from", "-", "."],
        ["--diff"],
        ["--diff-from", "-", "--diff-units", "all"],
        [],
    ],
)
@pytest.mark.usefixtures("project")
def test_command_lines_that_do_not_fit_are_refused(
    tmp_path: Path, options: list[str]
) -> None:
    with pytest.raises(SystemExit) as exit_info:
        run_structure_command(FakeJudge(), tmp_path, *options)

    assert exit_info.value.code == ExitCode.RUN_ERROR
