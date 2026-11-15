"""The stop hook on a session's change from its start commit, commits included."""

import json
from pathlib import Path

import pytest

from klint.cli.change_summary_stop_hook import SUMMARIES_PATH
from tests.support.change_summary import HypothesisJudge
from tests.support.git_repository import (
    commit_everything,
    create_repository,
    isolate_git,
    run_git,
    write_files,
)
from tests.support.git_summaries import (
    GREETER_UNIT_IDS,
    copy_greeter_summaries,
    create_greeter_repository,
)
from tests.support.stop_hook import (
    feed_session_start_event,
    feed_stop_event,
    write_summaries,
)

GREET_FILE_LINE = "- app/greet.py (modified): @@ -1 +0,0 @@, @@ -5 +4,2 @@"
GUIDE_FILE_LINE = "- docs/guide.md (added): @@ -0,0 +1 @@"


@pytest.fixture
def greeter(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    """Return the greeter repository, with its uncommitted change, as the cwd."""
    isolate_git(monkeypatch, tmp_path)
    monkeypatch.delenv("CLAUDE_PROJECT_DIR", raising=False)
    repository = create_greeter_repository(tmp_path / "greeter")
    monkeypatch.chdir(repository)
    return repository


def read_head(repository: Path) -> str:
    return run_git(repository, "rev-parse", "HEAD").strip()


def describe_base(commit: str) -> str:
    return f'"git_change": {json.dumps({"base": commit})}'


def test_a_session_start_records_nothing_the_agent_reads(greeter: Path) -> None:
    assert feed_session_start_event(greeter) == ""


def test_a_committed_change_is_checked_from_the_start_commit(greeter: Path) -> None:
    start = read_head(greeter)
    feed_session_start_event(greeter)
    commit_everything(greeter, "Greeting by the stripped name")

    answer = feed_stop_event(greeter, HypothesisJudge())

    assert answer.is_block
    assert answer.reason is not None
    assert f"git diff -U0 {start}, untracked files included" in answer.reason
    assert GREET_FILE_LINE in answer.reason
    assert GUIDE_FILE_LINE in answer.reason
    assert describe_base(start) in answer.reason
    assert "the commits made since, and the uncommitted change" in answer.reason


def test_summaries_naming_the_start_commit_let_the_agent_stop(greeter: Path) -> None:
    start = read_head(greeter)
    feed_session_start_event(greeter)
    commit_everything(greeter, "Greeting by the stripped name")
    summaries = copy_greeter_summaries()
    summaries["git_change"] = {"base": start}
    write_summaries(greeter, summaries)
    judge = HypothesisJudge()

    answer = feed_stop_event(greeter, judge)

    assert answer.is_plain_stop()
    assert len(judge.requests) == len(GREETER_UNIT_IDS)


def test_summaries_of_the_uncommitted_change_alone_block_naming_the_base(
    greeter: Path,
) -> None:
    start = read_head(greeter)
    feed_session_start_event(greeter)
    commit_everything(greeter, "Greeting by the stripped name")
    write_summaries(greeter)

    answer = feed_stop_event(greeter, HypothesisJudge())

    assert answer.is_block
    assert answer.reason is not None
    assert (
        f"The summaries in {SUMMARIES_PATH} must be of the current change: "
        f"summaries only, with {describe_base(start)}."
    ) in answer.reason


def test_an_uncommitted_change_is_checked_from_the_start_commit(greeter: Path) -> None:
    start = read_head(greeter)
    feed_session_start_event(greeter)

    answer = feed_stop_event(greeter, HypothesisJudge())

    assert answer.is_block
    assert answer.reason is not None
    assert f"git diff -U0 {start}, untracked files included" in answer.reason
    assert GREET_FILE_LINE in answer.reason
    assert GUIDE_FILE_LINE in answer.reason


def test_a_committed_and_an_uncommitted_change_are_checked_together(
    greeter: Path,
) -> None:
    start = read_head(greeter)
    feed_session_start_event(greeter)
    run_git(greeter, "add", "app/greet.py")
    run_git(greeter, "commit", "--quiet", "--message", "Greeting by the stripped name")
    assert run_git(greeter, "status", "--porcelain") == "?? docs/\n"
    summaries = copy_greeter_summaries()
    summaries["git_change"] = {"base": start}
    write_summaries(greeter, summaries)
    judge = HypothesisJudge()

    asked = feed_stop_event(greeter, HypothesisJudge())
    answer = feed_stop_event(greeter, judge, is_stop_hook_active=True)

    assert asked.is_plain_stop()
    assert answer.is_plain_stop()
    assert len(judge.requests) == len(GREETER_UNIT_IDS)


def test_a_session_that_commits_nothing_and_changes_nothing_may_stop(
    greeter: Path,
) -> None:
    commit_everything(greeter, "Greeting by the stripped name")
    feed_session_start_event(greeter)
    judge = HypothesisJudge()

    answer = feed_stop_event(greeter, judge)

    assert answer.is_plain_stop()
    assert judge.requests == []


def test_a_start_commit_rewritten_away_falls_back_to_the_uncommitted_change(
    greeter: Path,
) -> None:
    start = read_head(greeter)
    feed_session_start_event(greeter)
    run_git(greeter, "commit", "--quiet", "--amend", "--message", "Starting anew")
    commit_everything(greeter, "Greeting by the stripped name")

    answer = feed_stop_event(greeter, HypothesisJudge())

    assert not answer.is_block
    assert answer.warning == (
        f"The commit recorded at this session's start, {start[:12]}, is no longer "
        "in the current branch's history, as after a rebase, an amend or a branch "
        "switch. Only the uncommitted change is checked; a change committed since "
        "the start is not"
    )


def test_the_fallback_warns_the_user_while_blocking_the_agent(greeter: Path) -> None:
    feed_session_start_event(greeter)
    run_git(greeter, "commit", "--quiet", "--amend", "--message", "Starting anew")

    answer = feed_stop_event(greeter, HypothesisJudge())

    assert answer.is_block
    assert answer.reason is not None
    assert "git diff -U0 HEAD, untracked files included" in answer.reason
    assert '"git_change": {}' in answer.reason
    assert answer.warning is not None
    assert "is no longer in the current branch's history" in answer.warning


def test_two_sessions_each_keep_their_own_start_commit(greeter: Path) -> None:
    start_a = read_head(greeter)
    feed_session_start_event(greeter, session_id="session-a")
    run_git(greeter, "add", "app/greet.py")
    run_git(greeter, "commit", "--quiet", "--message", "Greeting by the stripped name")
    start_b = read_head(greeter)
    feed_session_start_event(greeter, session_id="session-b")

    answer_a = feed_stop_event(greeter, HypothesisJudge(), session_id="session-a")
    answer_b = feed_stop_event(greeter, HypothesisJudge(), session_id="session-b")

    assert answer_a.reason is not None
    assert answer_b.reason is not None
    assert GREET_FILE_LINE in answer_a.reason
    assert describe_base(start_a) in answer_a.reason
    assert GREET_FILE_LINE not in answer_b.reason
    assert GUIDE_FILE_LINE in answer_b.reason
    assert describe_base(start_b) in answer_b.reason


def test_a_resumed_session_keeps_the_commit_it_started_at(greeter: Path) -> None:
    start = read_head(greeter)
    feed_session_start_event(greeter)
    commit_everything(greeter, "Greeting by the stripped name")
    feed_session_start_event(greeter, source="resume")

    answer = feed_stop_event(greeter, HypothesisJudge())

    assert answer.is_block
    assert answer.reason is not None
    assert describe_base(start) in answer.reason


def test_a_repository_with_no_commit_yet_records_no_start(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    isolate_git(monkeypatch, tmp_path)
    monkeypatch.delenv("CLAUDE_PROJECT_DIR", raising=False)
    repository = tmp_path / "fresh"
    repository.mkdir()
    run_git(repository, "init", "--quiet", "--initial-branch", "main")
    monkeypatch.chdir(repository)
    feed_session_start_event(repository)
    write_files(repository, {"docs/guide.md": "Run greet(name).\n"})

    answer = feed_stop_event(repository, HypothesisJudge())

    assert answer.is_block
    assert answer.reason is not None
    assert GUIDE_FILE_LINE in answer.reason
    assert '"git_change": {}' in answer.reason


def test_the_start_commit_is_kept_outside_the_working_tree(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    isolate_git(monkeypatch, tmp_path)
    monkeypatch.delenv("CLAUDE_PROJECT_DIR", raising=False)
    repository = create_repository(tmp_path / "clean", {"README.md": "# Clean\n"})
    monkeypatch.chdir(repository)

    feed_session_start_event(repository)

    assert run_git(repository, "status", "--porcelain", "--untracked-files=all") == ""
    assert (
        repository / ".git/klint/change-summary-stop-hook/session-1/start-commit"
    ).exists()
