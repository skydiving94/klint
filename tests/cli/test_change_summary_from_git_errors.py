"""klint-change-summary stops with exit 2 when summaries and the git change disagree."""

from collections.abc import Callable
from pathlib import Path

import pytest

from klint.cli import ExitCode
from tests.support.change_summary import HypothesisJudge
from tests.support.git_repository import commit_everything, isolate_git, write_files
from tests.support.git_summaries import (
    SummariesData,
    copy_greeter_summaries,
    create_greeter_repository,
    verify_summaries,
)

Capture = pytest.CaptureFixture[str]
_ERROR_PREFIX = "[klint-change-summary] Error: "


@pytest.fixture
def greeter(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    """Return the greeter repository, with its uncommitted change, as the cwd."""
    isolate_git(monkeypatch, tmp_path)
    repository = create_greeter_repository(tmp_path / "greeter")
    monkeypatch.chdir(repository)
    return repository


def _summarize_a_hunk_not_in_the_change(summaries: SummariesData) -> None:
    summaries["files"][0]["hunks"][0]["header"] = "@@ -2 +2 @@"


def _summarize_a_file_not_in_the_change(summaries: SummariesData) -> None:
    summaries["files"][1]["path"] = "README.md"


def _summarize_a_package_not_in_the_change(summaries: SummariesData) -> None:
    summaries["packages"].append({"path": "lib", "summary": "Adds a library."})


def _summarize_the_root_as_a_package(summaries: SummariesData) -> None:
    summaries["packages"].append({"path": ".", "summary": "The commit."})


def _summarize_a_hunk_twice(summaries: SummariesData) -> None:
    summaries["files"][0]["hunks"].append(dict(summaries["files"][0]["hunks"][0]))


def _name_a_hunk_by_something_else(summaries: SummariesData) -> None:
    summaries["files"][0]["hunks"][0]["header"] = "hunk 1"


@pytest.mark.parametrize(
    ("break_summaries", "expected_error"),
    [
        (
            _summarize_a_hunk_not_in_the_change,
            "Change-summary document: #/files/0/hunks/0/header is '@@ -2 +2 @@', "
            "which is not a hunk of 'app/greet.py' in the change; its hunks are "
            "'@@ -1 +0,0 @@', '@@ -5 +4,2 @@'",
        ),
        (
            _summarize_a_file_not_in_the_change,
            "Change-summary document: #/files/1/path is 'README.md', which the "
            "change does not touch; it touches 'app/greet.py', 'docs/guide.md'",
        ),
        (
            _summarize_a_package_not_in_the_change,
            "Change-summary document: #/packages/1/path is 'lib', which holds no "
            "file of the change",
        ),
        (
            _summarize_the_root_as_a_package,
            "Change-summary document: #/packages/1/path is '.'; a package is a "
            "directory inside the repository. The commit's summary is the "
            "document's own summary",
        ),
        (
            _summarize_a_hunk_twice,
            "Change-summary document: #/files/0/hunks/2/header names a hunk the "
            "document has named before",
        ),
        (
            _name_a_hunk_by_something_else,
            "Change-summary document: #/files/0/hunks/0/header is 'hunk 1', which is "
            "not a hunk header such as '@@ -20,0 +21 @@', as git diff -U0 writes it",
        ),
    ],
)
def test_a_summary_of_something_the_change_does_not_hold_is_an_error(
    greeter: Path,
    capsys: Capture,
    break_summaries: Callable[[SummariesData], None],
    expected_error: str,
) -> None:
    summaries = copy_greeter_summaries()
    break_summaries(summaries)
    judge = HypothesisJudge()

    exit_code = verify_summaries(greeter / "summaries.json", judge, summaries)

    assert exit_code == ExitCode.RUN_ERROR
    assert capsys.readouterr().err.splitlines() == [_ERROR_PREFIX + expected_error]
    assert judge.requests == []


def test_a_hunk_summary_for_a_binary_file_is_an_error(
    greeter: Path, capsys: Capture
) -> None:
    commit_everything(greeter, "Greeting by the stripped name")
    write_files(greeter, {"logo.png": b"\x89PNG\r\n\x1a\n\x00\x00"})
    summaries = {
        "schema_version": 1,
        "git_change": {},
        "files": [
            {
                "path": "logo.png",
                "hunks": [{"header": "@@ -0,0 +1 @@", "summary": "Adds a logo."}],
            }
        ],
    }

    exit_code = verify_summaries(
        greeter.parent / "summaries.json", HypothesisJudge(), summaries
    )

    assert exit_code == ExitCode.RUN_ERROR
    assert capsys.readouterr().err.endswith(
        "which is not a hunk of 'logo.png' in the change; it has no hunk, as for "
        "a binary file or a rename without edits\n"
    )


def test_an_empty_change_is_an_error(greeter: Path, capsys: Capture) -> None:
    commit_everything(greeter, "Greeting by the stripped name")

    exit_code = verify_summaries(greeter.parent / "summaries.json", HypothesisJudge())

    assert exit_code == ExitCode.RUN_ERROR
    assert capsys.readouterr().err.splitlines() == [
        _ERROR_PREFIX + "The change (git diff -U0 HEAD, untracked files included) "
        "holds no changed file, so there is no summary to verify"
    ]


def test_an_unknown_commit_is_an_error(greeter: Path, capsys: Capture) -> None:
    summaries = copy_greeter_summaries()
    summaries["git_change"] = {"commit": "no-such-commit"}

    exit_code = verify_summaries(
        greeter / "summaries.json", HypothesisJudge(), summaries
    )

    assert exit_code == ExitCode.RUN_ERROR
    assert capsys.readouterr().err.splitlines() == [
        f"{_ERROR_PREFIX}The repository '{greeter.resolve()}' has no commit "
        "'no-such-commit'"
    ]


def test_a_directory_outside_any_repository_is_an_error(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: Capture
) -> None:
    isolate_git(monkeypatch, tmp_path)
    monkeypatch.setenv("GIT_CEILING_DIRECTORIES", str(tmp_path))
    outside = tmp_path / "outside"
    outside.mkdir()
    monkeypatch.chdir(outside)

    exit_code = verify_summaries(outside / "summaries.json", HypothesisJudge())

    assert exit_code == ExitCode.RUN_ERROR
    assert capsys.readouterr().err.startswith(
        f"{_ERROR_PREFIX}'{outside}' is not in a git repository: fatal: not a git "
        "repository"
    )
