"""klint-change-summary --instructions and --skeleton stop with exit 2 on bad input."""

import asyncio
import json
from collections.abc import Sequence
from pathlib import Path

import pytest

from klint.cli import CHANGE_SUMMARY_COMMAND, ExitCode
from tests.support.builders import build_audit_command_app
from tests.support.change_summary import HypothesisJudge
from tests.support.git_repository import create_repository, isolate_git

Capture = pytest.CaptureFixture[str]
_ERROR_PREFIX = "[klint-change-summary] Error: "
_SUMMARIES_ONLY = {"schema_version": 1, "git_change": {}, "files": []}


def _run_command(argv: Sequence[str]) -> tuple[ExitCode, HypothesisJudge]:
    judge = HypothesisJudge()
    app = build_audit_command_app(CHANGE_SUMMARY_COMMAND, judge)
    return asyncio.run(app.run(list(argv))), judge


def _read_error_line(capsys: Capture) -> str:
    (line,) = [
        line
        for line in capsys.readouterr().err.splitlines()
        if line.startswith(_ERROR_PREFIX)
    ]
    return line


def _check_summaries_only(directory: Path, capsys: Capture) -> str:
    """Return the error klint-change-summary gives for summaries in ``directory``."""
    summaries_path = directory / "summaries.json"
    summaries_path.write_text(json.dumps(_SUMMARIES_ONLY), encoding="utf-8")
    exit_code, _ = _run_command([str(summaries_path)])
    summaries_path.unlink()
    assert exit_code == ExitCode.RUN_ERROR
    return _read_error_line(capsys)


@pytest.fixture
def clean_project(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    """Return a repository with nothing changed since its commit, as the cwd."""
    isolate_git(monkeypatch, tmp_path)
    repository = create_repository(tmp_path / "project", {"app.py": "x = 1\n"})
    monkeypatch.chdir(repository)
    return repository


@pytest.fixture
def plain_folder(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    """Return a folder outside any git repository, as the cwd."""
    isolate_git(monkeypatch, tmp_path)
    monkeypatch.setenv("GIT_CEILING_DIRECTORIES", str(tmp_path))
    folder = tmp_path / "plain"
    folder.mkdir()
    monkeypatch.chdir(folder)
    return folder


def test_an_empty_change_has_no_skeleton(clean_project: Path, capsys: Capture) -> None:
    expected_error = _check_summaries_only(clean_project, capsys)

    exit_code, judge = _run_command(["--skeleton"])

    assert exit_code == ExitCode.RUN_ERROR
    assert judge.requests == []
    assert _read_error_line(capsys) == expected_error
    assert "holds no changed file" in expected_error


def test_a_folder_outside_git_has_no_skeleton(
    plain_folder: Path, capsys: Capture
) -> None:
    expected_error = _check_summaries_only(plain_folder, capsys)

    exit_code, _ = _run_command(["--skeleton"])

    assert exit_code == ExitCode.RUN_ERROR
    assert _read_error_line(capsys) == expected_error
    assert "is not in a git repository" in expected_error


@pytest.mark.usefixtures("clean_project")
def test_an_unknown_commit_has_no_skeleton(capsys: Capture) -> None:
    exit_code, _ = _run_command(["--skeleton", "no-such-commit"])

    assert exit_code == ExitCode.RUN_ERROR
    assert "no-such-commit" in _read_error_line(capsys)


@pytest.mark.parametrize(
    ("argv", "expected_error"),
    [
        (
            ["summaries.json", "--skeleton"],
            "--skeleton takes no path to summaries",
        ),
        (
            ["summaries.json", "--instructions"],
            "--instructions takes no path to summaries",
        ),
        (
            ["--instructions", "--skeleton"],
            "--skeleton: not allowed with argument --instructions",
        ),
        ([], "a path to the summaries, --instructions or --skeleton is required"),
    ],
)
def test_a_clashing_command_line_is_refused_with_a_usage_line(
    capsys: Capture, argv: list[str], expected_error: str
) -> None:
    with pytest.raises(SystemExit) as stop:
        _run_command(argv)

    error_output = capsys.readouterr().err
    assert stop.value.code == ExitCode.RUN_ERROR
    assert error_output.startswith("usage: ")
    assert expected_error in error_output
