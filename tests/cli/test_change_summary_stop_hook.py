"""The change-summary stop hook's answer to a Stop event, for each kind of outcome."""

from pathlib import Path

import pytest

from klint.cli.change_summary_stop_hook import (
    MAX_BLOCKS_IN_A_ROW,
    SUMMARIES_PATH,
    load_summary_instructions,
)
from tests.support.change_summary import HypothesisJudge
from tests.support.fakes import PickyJudge
from tests.support.git_repository import commit_everything, isolate_git, write_files
from tests.support.git_summaries import (
    GREETER_SUMMARIES,
    GREETER_UNIT_IDS,
    IMPORT_HUNK,
    copy_greeter_summaries,
    create_greeter_repository,
)
from tests.support.stop_hook import feed_stop_event, write_summaries

# The judge flags the summary of the hunk that removes the import as false.
FLAGGING_JUDGE_PHRASES = {"Removes the unused": {"no_false_statement": "inaccurate"}}


@pytest.fixture
def greeter(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    """Return the greeter repository, with its uncommitted change, as the cwd."""
    isolate_git(monkeypatch, tmp_path)
    monkeypatch.delenv("CLAUDE_PROJECT_DIR", raising=False)
    repository = create_greeter_repository(tmp_path / "greeter")
    monkeypatch.chdir(repository)
    return repository


def test_no_change_lets_the_agent_stop(greeter: Path) -> None:
    commit_everything(greeter, "Greeting by the stripped name")
    judge = HypothesisJudge()

    answer = feed_stop_event(greeter, judge)

    assert answer.is_plain_stop()
    assert judge.requests == []


def test_no_summaries_block_with_the_change_and_the_instructions(
    greeter: Path,
) -> None:
    answer = feed_stop_event(greeter, HypothesisJudge())

    assert answer.is_block
    assert answer.reason is not None
    assert f"write summaries of your change to {SUMMARIES_PATH}" in answer.reason
    assert "- app/greet.py (modified): @@ -1 +0,0 @@, @@ -5 +4,2 @@" in answer.reason
    assert "- docs/guide.md (added): @@ -0,0 +1 @@" in answer.reason
    assert load_summary_instructions() in answer.reason


def test_summaries_out_of_date_for_the_change_block_naming_the_difference(
    greeter: Path,
) -> None:
    write_summaries(greeter)
    write_files(greeter, {"app/greet.py": "def greet(name):\n    return name\n"})

    answer = feed_stop_event(greeter, HypothesisJudge())

    assert answer.is_block
    assert answer.reason is not None
    assert "are not those of the current change" in answer.reason
    assert (
        "Not summarized:\n- app/greet.py @@ -1,3 +0,0 @@\n- app/greet.py @@ -5 +2 @@"
    ) in answer.reason
    assert (
        "Summarized but not in the change:\n- app/greet.py @@ -1 +0,0 @@\n"
        "- app/greet.py @@ -5 +4,2 @@"
    ) in answer.reason


def test_summaries_of_a_commit_block_asking_for_the_uncommitted_change(
    greeter: Path,
) -> None:
    summaries = copy_greeter_summaries()
    summaries["git_change"] = {"commit": "HEAD"}
    write_summaries(greeter, summaries)

    answer = feed_stop_event(greeter, HypothesisJudge())

    assert answer.is_block
    assert answer.reason is not None
    assert 'with "git_change": {}' in answer.reason


def test_summaries_that_all_pass_let_the_agent_stop(greeter: Path) -> None:
    write_summaries(greeter)
    judge = HypothesisJudge()

    answer = feed_stop_event(greeter, judge)

    assert answer.is_plain_stop()
    assert len(judge.requests) == len(GREETER_UNIT_IDS)


def test_flagged_summaries_block_listing_each_one_and_its_failed_checks(
    greeter: Path,
) -> None:
    write_summaries(greeter)

    answer = feed_stop_event(greeter, HypothesisJudge(FLAGGING_JUDGE_PHRASES))

    assert answer.is_block
    assert answer.reason is not None
    assert answer.reason.startswith(
        f"klint flagged 1 of the summaries in {SUMMARIES_PATH}."
    )
    assert (
        "- The hunk summary of app/greet.py#1 at #/files/0/hunks/0/summary: "
        f'"{IMPORT_HUNK["summary"]}"\n'
        "  - no_false_statement: Inaccurate, 90% confident. Asked: How does the "
        "hypothesis relate to the premise?"
    ) in answer.reason


def test_a_summary_left_blank_blocks_as_a_failed_check(greeter: Path) -> None:
    summaries = copy_greeter_summaries()
    summaries["files"][1]["summary"] = None
    write_summaries(greeter, summaries)

    answer = feed_stop_event(greeter, HypothesisJudge())

    assert answer.is_block
    assert answer.reason is not None
    assert (
        "- The file summary of docs/guide.md at #/files/1/summary: no summary\n"
        "  - has_summary: Inaccurate. Asked: Is there a summary?"
    ) in answer.reason


@pytest.mark.parametrize(
    ("summaries", "error"),
    [
        ("{not json", "is not valid JSON"),
        (
            {**GREETER_SUMMARIES, "summary": 7},
            "Change-summary document: #/summary must be text that is not blank",
        ),
        (
            {**GREETER_SUMMARIES, "packages": [{"path": "lib", "summary": "Lib."}]},
            "#/packages/0/path is 'lib', which holds no file of the change",
        ),
    ],
)
def test_malformed_summaries_block_with_klints_error(
    greeter: Path, summaries: object, error: str
) -> None:
    write_summaries(greeter, summaries)

    answer = feed_stop_event(greeter, HypothesisJudge())

    assert answer.is_block
    assert answer.reason is not None
    assert answer.reason.startswith(f"klint cannot read {SUMMARIES_PATH}: ")
    assert error in answer.reason


def test_a_judge_that_is_down_lets_the_agent_stop_with_a_warning(
    greeter: Path,
) -> None:
    write_summaries(greeter)

    answer = feed_stop_event(greeter, PickyJudge(refuses="Hypothesis: "))

    assert not answer.is_block
    assert answer.warning is not None
    assert answer.warning.startswith(
        "klint could not check the change summaries, so the agent may stop: "
        f"{len(GREETER_UNIT_IDS)} of the {len(GREETER_UNIT_IDS)} summaries could "
        "not be checked; "
    )
    assert "judge is down" in answer.warning
    assert "Judge: " in answer.warning


def test_a_project_outside_git_lets_the_agent_stop_with_a_warning(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    isolate_git(monkeypatch, tmp_path)
    monkeypatch.setenv("GIT_CEILING_DIRECTORIES", str(tmp_path))
    project = tmp_path / "project"
    project.mkdir()

    answer = feed_stop_event(project, HypothesisJudge())

    assert not answer.is_block
    assert answer.warning is not None
    assert "is not in a git repository" in answer.warning


def test_after_the_most_blocks_in_a_row_the_agent_may_stop_with_a_warning(
    greeter: Path,
) -> None:
    write_summaries(greeter)
    judge = HypothesisJudge(FLAGGING_JUDGE_PHRASES)

    answers = [
        feed_stop_event(greeter, judge, is_stop_hook_active=index > 0)
        for index in range(MAX_BLOCKS_IN_A_ROW + 2)
    ]

    assert [answer.is_block for answer in answers] == [
        *[True] * MAX_BLOCKS_IN_A_ROW,
        False,
        True,
    ]
    gave_up = answers[MAX_BLOCKS_IN_A_ROW].warning
    assert gave_up is not None
    assert gave_up.startswith(
        "klint's change-summary stop hook blocked this session's stop "
        f"{MAX_BLOCKS_IN_A_ROW} times in a row, so it let the agent stop."
    )
    assert "app/greet.py#1" in gave_up
