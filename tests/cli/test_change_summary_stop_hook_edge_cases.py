"""The change-summary stop hook across sessions, with its files, options and limits."""

import asyncio
import json
from pathlib import Path

import pytest

from klint.cli import ChangeSummaryStopHook
from klint.cli.change_summary_stop_hook import MAX_BLOCKS_IN_A_ROW, SUMMARIES_PATH
from tests.support.change_summary import HypothesisJudge
from tests.support.git_repository import isolate_git, run_git, write_files
from tests.support.git_summaries import (
    copy_greeter_summaries,
    create_greeter_repository,
)
from tests.support.stop_hook import feed_stop_event, write_summaries

FLAGGING_JUDGE_PHRASES = {"Removes the unused": {"no_false_statement": "inaccurate"}}


@pytest.fixture
def greeter(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    """Return the greeter repository, with its uncommitted change, as the cwd."""
    isolate_git(monkeypatch, tmp_path)
    monkeypatch.delenv("CLAUDE_PROJECT_DIR", raising=False)
    repository = create_greeter_repository(tmp_path / "greeter")
    monkeypatch.chdir(repository)
    return repository


def block_until_the_cap(greeter: Path, judge: HypothesisJudge, session_id: str) -> None:
    """Have the hook block the session's stops as many times in a row as it may."""
    for index in range(MAX_BLOCKS_IN_A_ROW):
        answer = feed_stop_event(
            greeter, judge, session_id=session_id, is_stop_hook_active=index > 0
        )
        assert answer.is_block


def test_blocks_are_counted_per_session(greeter: Path) -> None:
    write_summaries(greeter)
    judge = HypothesisJudge(FLAGGING_JUDGE_PHRASES)
    block_until_the_cap(greeter, judge, "session-a")

    other_session = feed_stop_event(greeter, judge, session_id="session-b")
    same_session = feed_stop_event(
        greeter, judge, session_id="session-a", is_stop_hook_active=True
    )

    assert other_session.is_block
    assert not same_session.is_block
    assert same_session.warning is not None


def test_a_stop_that_follows_no_block_starts_the_count_again(greeter: Path) -> None:
    write_summaries(greeter)
    judge = HypothesisJudge(FLAGGING_JUDGE_PHRASES)
    block_until_the_cap(greeter, judge, "session-1")

    answer = feed_stop_event(greeter, judge, is_stop_hook_active=False)

    assert answer.is_block


def test_fixed_summaries_let_the_agent_stop_and_start_the_count_again(
    greeter: Path,
) -> None:
    write_summaries(greeter)
    flagging_judge = HypothesisJudge(FLAGGING_JUDGE_PHRASES)
    assert feed_stop_event(greeter, flagging_judge).is_block
    summaries = copy_greeter_summaries()
    summaries["files"][0]["hunks"][0]["summary"] = "Drops the import of os."
    write_summaries(greeter, summaries)

    fixed = feed_stop_event(greeter, flagging_judge, is_stop_hook_active=True)
    write_summaries(greeter)
    answers = [
        feed_stop_event(greeter, flagging_judge, is_stop_hook_active=True)
        for _ in range(MAX_BLOCKS_IN_A_ROW)
    ]

    assert fixed.is_plain_stop()
    assert all(answer.is_block for answer in answers)


def test_the_hooks_own_files_stay_out_of_the_change(greeter: Path) -> None:
    status_before = run_git(greeter, "status", "--porcelain", "--untracked-files=all")
    assert feed_stop_event(greeter, HypothesisJudge()).is_block
    write_summaries(greeter)

    answer = feed_stop_event(greeter, HypothesisJudge(), is_stop_hook_active=True)

    assert answer.is_plain_stop()
    assert (greeter / SUMMARIES_PATH.parent / ".gitignore").exists()
    assert (
        run_git(greeter, "status", "--porcelain", "--untracked-files=all")
        == status_before
    )


def test_findings_below_the_min_confidence_let_the_agent_stop(greeter: Path) -> None:
    write_summaries(greeter)

    answer = feed_stop_event(
        greeter,
        HypothesisJudge(FLAGGING_JUDGE_PHRASES),
        options=["--min-confidence", "0.95"],
    )

    assert answer.is_plain_stop()


def test_options_the_hook_does_not_know_let_the_agent_stop_with_a_warning(
    greeter: Path,
) -> None:
    answer = feed_stop_event(greeter, HypothesisJudge(), options=["--no-such"])

    assert not answer.is_block
    assert answer.warning is not None
    assert "are not valid" in answer.warning


def test_the_project_directory_claude_code_names_is_the_one_checked(
    greeter: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(greeter))
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()

    answer = feed_stop_event(elsewhere, HypothesisJudge())

    assert answer.is_block
    assert answer.reason is not None
    assert "docs/guide.md (added)" in answer.reason


def test_a_long_reason_is_cut_to_what_claude_code_reads(greeter: Path) -> None:
    long_summary = "Adds a note, flagged. " * 20
    notes = {f"notes/note_{index}.md": f"Note {index}.\n" for index in range(30)}
    write_files(greeter, notes)
    summaries = copy_greeter_summaries()
    for path in notes:
        summaries["files"].append(
            {
                "path": path,
                "summary": long_summary,
                "hunks": [{"header": "@@ -0,0 +1 @@", "summary": long_summary}],
            }
        )
    write_summaries(greeter, summaries)
    judge = HypothesisJudge({"flagged": {"no_false_statement": "inaccurate"}})

    answer = feed_stop_event(greeter, judge)

    assert answer.is_block
    assert len(answer.output) <= 10_000
    assert answer.reason is not None
    assert answer.reason.endswith(
        "cut to fit what Claude Code reads of a hook's output]"
    )


@pytest.mark.usefixtures("greeter")
def test_an_event_that_is_not_json_lets_the_agent_stop_with_a_warning() -> None:
    output = json.loads(asyncio.run(ChangeSummaryStopHook().respond([], "not json")))

    assert output["systemMessage"].endswith(
        "ValueError: The Stop event is not valid JSON: Expecting value: line 1 "
        "column 1 (char 0)."
    )


def test_the_projects_klint_json_chooses_the_judge(greeter: Path) -> None:
    write_files(greeter, {"klint.json": '{"env": {"KLINT_JUDGE_MODE": "bogus"}}'})
    run_git(greeter, "add", "klint.json")
    run_git(greeter, "commit", "--quiet", "--message", "Choosing a judge")
    write_summaries(greeter)

    answer = feed_stop_event(greeter, HypothesisJudge())

    assert not answer.is_block
    assert answer.warning is not None
    assert "KLINT_JUDGE_MODE 'bogus' set in" in answer.warning
    assert "klint.json" in answer.warning
