"""klint-change-summary --instructions and --skeleton: what an agent starts from."""

import asyncio
import json
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import pytest

from klint.cli import CHANGE_SUMMARY_COMMAND, ExitCode
from klint.cli.change_summary_writing import (
    InstructionsAudience,
    load_summary_instructions,
)
from tests.support.builders import build_audit_command_app
from tests.support.change_summary import HypothesisJudge
from tests.support.git_repository import (
    commit_everything,
    isolate_git,
    run_git,
    write_files,
)
from tests.support.git_summaries import create_greeter_repository, verify_summaries

Capture = pytest.CaptureFixture[str]
SkeletonData = dict[str, Any]


@pytest.fixture
def greeter(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    """Return the greeter repository, with its uncommitted change, as the cwd."""
    isolate_git(monkeypatch, tmp_path)
    repository = create_greeter_repository(tmp_path / "greeter")
    monkeypatch.chdir(repository)
    return repository


def _run_command(argv: Sequence[str], judge: HypothesisJudge) -> ExitCode:
    app = build_audit_command_app(CHANGE_SUMMARY_COMMAND, judge)
    return asyncio.run(app.run(list(argv)))


def _print_skeleton(argv: Sequence[str], capsys: Capture) -> SkeletonData:
    judge = HypothesisJudge()
    exit_code = _run_command(["--skeleton", *argv], judge)
    assert exit_code == ExitCode.NO_PROBLEMS
    assert judge.requests == []
    skeleton: SkeletonData = json.loads(capsys.readouterr().out)
    return skeleton


def _list_parts(skeleton: SkeletonData) -> list[tuple[str, list[str]]]:
    return [
        (file["path"], [hunk["header"] for hunk in file["hunks"]])
        for file in skeleton["files"]
    ]


def _fill(skeleton: SkeletonData) -> SkeletonData:
    """Return the skeleton with a summary in each place, and no other edit."""
    skeleton["summary"] = "Changes the project."
    for file in skeleton["files"]:
        file["summary"] = f"Changes {file['path']}."
        for hunk in file["hunks"]:
            hunk["summary"] = f"Changes the lines at {hunk['header']}."
    return skeleton


def test_instructions_are_printed_for_any_agent_without_asking_the_judge(
    capsys: Capture,
) -> None:
    judge = HypothesisJudge()

    exit_code = _run_command(["--instructions"], judge)

    output = capsys.readouterr().out
    assert exit_code == ExitCode.NO_PROBLEMS
    assert judge.requests == []
    assert output.strip() == load_summary_instructions(InstructionsAudience.ANY_AGENT)
    assert "as this message says above" not in output
    assert "--skeleton" in output


@pytest.mark.usefixtures("greeter")
def test_the_skeleton_of_the_uncommitted_change_lists_every_file_and_hunk(
    capsys: Capture,
) -> None:
    skeleton = _print_skeleton([], capsys)

    assert skeleton["schema_version"] == 1
    assert skeleton["git_change"] == {}
    assert skeleton["summary"] is None
    assert skeleton["packages"] == []
    assert _list_parts(skeleton) == [
        ("app/greet.py", ["@@ -1 +0,0 @@", "@@ -5 +4,2 @@"]),
        ("docs/guide.md", ["@@ -0,0 +1 @@"]),
    ]
    summaries = [file["summary"] for file in skeleton["files"]] + [
        hunk["summary"] for file in skeleton["files"] for hunk in file["hunks"]
    ]
    assert summaries == [None] * 5


def test_the_skeleton_of_a_commit_names_it_and_lists_its_files_and_hunks(
    greeter: Path, capsys: Capture
) -> None:
    commit_everything(greeter, "Greeting by the stripped name")

    skeleton = _print_skeleton(["HEAD"], capsys)

    assert skeleton["git_change"] == {"commit": "HEAD"}
    assert _list_parts(skeleton) == [
        ("app/greet.py", ["@@ -1 +0,0 @@", "@@ -5 +4,2 @@"]),
        ("docs/guide.md", ["@@ -0,0 +1 @@"]),
    ]


def test_a_binary_file_and_a_rename_without_edits_are_listed_with_no_hunk(
    greeter: Path, capsys: Capture
) -> None:
    write_files(greeter, {"logo.png": b"\x89PNG\x00\x01"})
    run_git(greeter, "mv", "README.md", "README.txt")

    skeleton = _print_skeleton([], capsys)

    assert ("logo.png", []) in _list_parts(skeleton)
    assert ("README.txt", []) in _list_parts(skeleton)


@pytest.mark.parametrize("commit", [[], ["HEAD"]], ids=["uncommitted", "commit"])
def test_a_filled_skeleton_passes_the_coverage_checks(
    greeter: Path, capsys: Capture, commit: list[str]
) -> None:
    write_files(greeter, {"logo.png": b"\x89PNG\x00\x01"})
    run_git(greeter, "mv", "README.md", "README.txt")
    if commit:
        commit_everything(greeter, "Greeting by the stripped name")
    filled = _fill(_print_skeleton(commit, capsys))

    exit_code = verify_summaries(greeter / "summaries.json", HypothesisJudge(), filled)

    output = json.loads(capsys.readouterr().out)
    assert exit_code == ExitCode.NO_PROBLEMS
    assert "logo.png" in output["examined_summaries"]
    assert "README.txt" in output["examined_summaries"]


def test_an_unfilled_skeleton_fails_has_summary_on_every_part(
    greeter: Path, capsys: Capture
) -> None:
    skeleton = _print_skeleton([], capsys)
    judge = HypothesisJudge()

    exit_code = verify_summaries(greeter / "summaries.json", judge, skeleton)

    output = json.loads(capsys.readouterr().out)
    assert exit_code == ExitCode.PROBLEMS_FOUND
    assert judge.requests == []
    assert [
        (finding["unit_id"], finding["rule_id"]) for finding in output["findings"]
    ] == [
        ("./", "has_summary"),
        ("app/greet.py", "has_summary"),
        ("app/greet.py#1", "has_summary"),
        ("app/greet.py#2", "has_summary"),
        ("docs/guide.md", "has_summary"),
        ("docs/guide.md#1", "has_summary"),
    ]
