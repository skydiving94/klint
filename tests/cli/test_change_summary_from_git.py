"""klint-change-summary on summaries only, with the change read from git."""

import json
from pathlib import Path

import pytest

from klint.cli import ExitCode
from tests.support.change_summary import HypothesisJudge
from tests.support.git_repository import (
    commit_everything,
    isolate_git,
    run_git,
    write_files,
)
from tests.support.git_summaries import (
    GREETER_UNIT_IDS,
    copy_greeter_summaries,
    create_greeter_repository,
    verify_summaries,
)

Capture = pytest.CaptureFixture[str]


@pytest.fixture
def greeter(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    """Return the greeter repository, with its uncommitted change, as the cwd."""
    isolate_git(monkeypatch, tmp_path)
    repository = create_greeter_repository(tmp_path / "greeter")
    monkeypatch.chdir(repository)
    return repository


def test_summaries_of_the_uncommitted_change_are_verified_against_git(
    greeter: Path, capsys: Capture
) -> None:
    judge = HypothesisJudge()

    exit_code = verify_summaries(greeter / "summaries.json", judge)

    output = json.loads(capsys.readouterr().out)
    assert exit_code == ExitCode.NO_PROBLEMS
    assert output["examined_summaries"] == GREETER_UNIT_IDS
    assert judge.find_subject("Says to run greet(name).").splitlines()[:3] == [
        "Premise: this code change to docs/guide.md (added); a line starting "
        "with - is removed, with + is added.",
        "@@ -0,0 +1 @@",
        "+Run greet(name).",
    ]
    assert run_git(greeter, "status", "--porcelain") == (
        " M app/greet.py\n?? docs/\n?? summaries.json\n"
    )


def test_summaries_of_a_commit_are_verified_against_git(
    greeter: Path, tmp_path: Path, capsys: Capture
) -> None:
    commit_everything(greeter, "Greeting by the stripped name")
    summaries = copy_greeter_summaries()
    summaries["git_change"] = {"commit": "HEAD"}

    exit_code = verify_summaries(
        tmp_path / "summaries.json", HypothesisJudge(), summaries
    )

    assert exit_code == ExitCode.NO_PROBLEMS
    assert json.loads(capsys.readouterr().out)["examined_summaries"] == (
        GREETER_UNIT_IDS
    )


def test_a_hunk_with_no_summary_is_a_finding_the_judge_is_not_asked(
    greeter: Path, capsys: Capture
) -> None:
    summaries = copy_greeter_summaries()
    del summaries["files"][0]["hunks"][1]
    judge = HypothesisJudge()

    exit_code = verify_summaries(greeter / "summaries.json", judge, summaries)

    output = json.loads(capsys.readouterr().out)
    assert exit_code == ExitCode.PROBLEMS_FOUND
    (finding,) = output["findings"]
    assert (finding["unit_id"], finding["rule_id"], finding["answer"]) == (
        "app/greet.py#2",
        "has_summary",
        "Inaccurate",
    )
    assert finding["confidence"] is None
    assert finding["location"] is None
    assert finding["evidence_location"]["path"] == "app/greet.py"
    assert finding["context"]["summary"] is None
    assert output["unit_id_to_roll_up_status"]["./"] == "descendant_problem"
    assert len(judge.requests) == len(GREETER_UNIT_IDS) - 1
    assert "- Hunk 2: no summary was written" in judge.find_subject(
        "Greets a stripped name with 'Hello, <name>!' and drops an unused import."
    )


def test_a_file_and_a_commit_with_no_summary_are_findings(
    greeter: Path, capsys: Capture
) -> None:
    summaries = copy_greeter_summaries()
    del summaries["summary"]
    del summaries["files"][1]

    exit_code = verify_summaries(
        greeter / "summaries.json", HypothesisJudge(), summaries
    )

    output = json.loads(capsys.readouterr().out)
    assert exit_code == ExitCode.PROBLEMS_FOUND
    assert [
        (finding["unit_id"], finding["rule_id"]) for finding in output["findings"]
    ] == [
        ("./", "has_summary"),
        ("docs/guide.md", "has_summary"),
        ("docs/guide.md#1", "has_summary"),
    ]
    assert output["examined_summaries"] == GREETER_UNIT_IDS


def test_a_renamed_file_is_summarized_by_its_new_path(
    greeter: Path, capsys: Capture
) -> None:
    commit_everything(greeter, "Greeting by the stripped name")
    run_git(greeter, "mv", "app/greet.py", "app/hello.py")
    write_files(
        greeter,
        {
            "app/hello.py": (greeter / "app/hello.py").read_text()
            + "\nWORLD = 'world'\n"
        },
    )
    summaries = {
        "schema_version": 1,
        "git_change": {},
        "summary": "Renames the greeter module and adds a WORLD constant.",
        "files": [
            {
                "path": "app/hello.py",
                "summary": "Renames greet.py to hello.py and adds WORLD.",
                "hunks": [
                    {"header": "@@ -5,0 +6,2 @@", "summary": "Adds WORLD = 'world'."}
                ],
            }
        ],
    }
    judge = HypothesisJudge()

    exit_code = verify_summaries(greeter.parent / "summaries.json", judge, summaries)

    assert exit_code == ExitCode.NO_PROBLEMS, capsys.readouterr().err
    assert json.loads(capsys.readouterr().out)["examined_summaries"] == [
        "./",
        "app/hello.py",
        "app/hello.py#1",
    ]
    assert "to app/hello.py (renamed from app/greet.py)" in judge.find_subject(
        "Adds WORLD = 'world'."
    )


def test_a_binary_file_has_a_summary_and_no_hunk(
    greeter: Path, capsys: Capture
) -> None:
    commit_everything(greeter, "Greeting by the stripped name")
    write_files(greeter, {"logo.png": b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR"})
    summaries = {
        "schema_version": 1,
        "git_change": {},
        "summary": "Adds a logo.",
        "files": [{"path": "logo.png", "summary": "Adds the logo image."}],
    }
    judge = HypothesisJudge()

    exit_code = verify_summaries(greeter.parent / "summaries.json", judge, summaries)

    assert exit_code == ExitCode.NO_PROBLEMS, capsys.readouterr().err
    assert json.loads(capsys.readouterr().out)["examined_summaries"] == [
        "./",
        "logo.png",
    ]
    assert "logo.png (added) adds and removes no line" in judge.find_subject(
        "Adds the logo image."
    )


def test_a_deleted_file_has_hunks_that_only_remove_lines(
    greeter: Path, capsys: Capture
) -> None:
    commit_everything(greeter, "Greeting by the stripped name")
    run_git(greeter, "rm", "--quiet", "docs/guide.md")
    summaries = {
        "schema_version": 1,
        "git_change": {},
        "summary": "Removes the guide.",
        "files": [
            {
                "path": "docs/guide.md",
                "summary": "Deletes the guide.",
                "hunks": [{"header": "@@ -1 +0,0 @@", "summary": "Removes the line."}],
            }
        ],
    }

    exit_code = verify_summaries(
        greeter.parent / "summaries.json",
        HypothesisJudge(),
        summaries,
        options=("--json", "--all-answers"),
    )

    findings = json.loads(capsys.readouterr().out)["findings"]
    assert exit_code == ExitCode.NO_PROBLEMS
    assert {
        json.dumps(finding["evidence_location"])
        for finding in findings
        if finding["unit_id"] == "docs/guide.md#1"
    } == {json.dumps({"path": "docs/guide.md", "start_line": 1, "end_line": 1})}
