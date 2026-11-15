"""The change-summary scoring command, run on small case sets with a fake judge."""

from pathlib import Path

import pytest

from judge_accuracy.change_summary.scoring_command import ScoringExitCode
from klint.core.models.judging import JudgeReply, JudgeRequest
from tests.judge_accuracy.scoring import (
    FALSE_IMPORT_MISTAKE,
    FALSE_IMPORT_SUMMARY,
    REASON_MISTAKE,
    find_table_row,
    run_scoring_command,
    write_case_file,
)
from tests.support.change_summary import (
    HYPOTHESIS_PREFIX,
    HypothesisJudge,
    copy_greeting_document,
)
from tests.support.fakes import CountingJudge, build_unreported_reply

Capture = pytest.CaptureFixture[str]
_FLAG_FALSE_IMPORT = {"import of sys": {"no_false_statement": "inaccurate"}}


@pytest.fixture(autouse=True)
def _private_environment(shell_env: dict[str, str]) -> None:
    del shell_env


def test_a_planted_mistake_the_judge_flags_is_caught(
    tmp_path: Path, capsys: Capture
) -> None:
    write_case_file(tmp_path, "greeting", FALSE_IMPORT_MISTAKE)

    exit_code = run_scoring_command(HypothesisJudge(_FLAG_FALSE_IMPORT), tmp_path)

    report = capsys.readouterr().out
    assert exit_code == ScoringExitCode.SCORED
    assert "1 case files: 7 true summaries, 1 planted mistakes" in report
    assert find_table_row(report, "False statement") == [
        "False statement",
        "1",
        "0",
        "1/1 (100%)",
        "1/1 (100%)",
        "0/4 (0%)",
    ]
    assert find_table_row(report, "Every check")[1:3] == ["7", "0/7 (0%)"]
    assert "Mistakes missed" not in report


def test_a_mistake_the_judge_misses_is_listed(tmp_path: Path, capsys: Capture) -> None:
    write_case_file(tmp_path, "greeting", FALSE_IMPORT_MISTAKE, REASON_MISTAKE)

    run_scoring_command(HypothesisJudge(_FLAG_FALSE_IMPORT), tmp_path)

    report = capsys.readouterr().out
    assert find_table_row(report, "Unsupported reason")[3] == "0/1 (0%)"
    assert find_table_row(report, "Every kind")[3] == "1/2 (50%)"
    assert (
        "### Mistakes missed (1)\n\n"
        "- `greeting` package `app/` (unsupported reason, planted 2)"
    ) in report


def test_a_mistake_caught_by_another_check_is_not_caught_by_its_own(
    tmp_path: Path, capsys: Capture
) -> None:
    write_case_file(tmp_path, "greeting", REASON_MISTAKE)
    judge = HypothesisJudge({"as users asked": {"covers_every_change": "inaccurate"}})

    run_scoring_command(judge, tmp_path)

    row = find_table_row(capsys.readouterr().out, "Unsupported reason")
    assert row[3:5] == ["1/1 (100%)", "0/1 (0%)"]


def test_a_true_summary_the_judge_flags_is_listed_with_its_failed_checks(
    tmp_path: Path, capsys: Capture
) -> None:
    write_case_file(tmp_path, "greeting")
    judge = HypothesisJudge(
        {"drops an unused import": {"covers_key_changes": "inaccurate"}}
    )

    run_scoring_command(judge, tmp_path)

    report = capsys.readouterr().out
    assert find_table_row(report, "Omission (covers_every_change, covers_key_changes)")[
        1:4
    ] == ["7", "1/7 (14%)", "0/14 (0%)"]
    assert find_table_row(report, "file") == ["file", "-", "1/2 (50%)"]
    assert (
        "- `greeting` file `app/greet.py` (true) - failed covers_key_changes 0.90"
    ) in report


def test_cannot_tell_answers_are_counted_per_kind(
    tmp_path: Path, capsys: Capture
) -> None:
    write_case_file(tmp_path, "greeting")
    judge = HypothesisJudge(
        {"Removes the unused import": {"no_false_statement": "cannot_tell"}}
    )

    run_scoring_command(judge, tmp_path)

    report = capsys.readouterr().out
    assert find_table_row(report, "False statement (no_false_statement)")[1:] == [
        "7",
        "0/7 (0%)",
        "1/7 (14%)",
    ]
    assert find_table_row(report, "Every check")[3] == "1/32 (3%)"


def test_a_refused_summary_is_a_refusal_not_a_miss(
    tmp_path: Path, capsys: Capture
) -> None:
    write_case_file(tmp_path, "greeting", FALSE_IMPORT_MISTAKE, REASON_MISTAKE)
    judge = HypothesisJudge(refused_phrases=frozenset({FALSE_IMPORT_SUMMARY}))

    exit_code = run_scoring_command(judge, tmp_path)

    captured = capsys.readouterr()
    assert exit_code == ScoringExitCode.SCORED
    assert find_table_row(captured.out, "False statement")[1:4] == ["1", "1", "-"]
    assert "Mistakes missed (1)" in captured.out
    assert (
        "### Refused (1)\n\n"
        "- `greeting` hunk `app/greet.py#2` (false statement, planted 1)"
    ) in captured.out
    assert "[judge-accuracy] Refused app/greet.py#2: judge is down" in captured.err


def test_a_set_the_judge_refuses_entirely_ends_with_exit_2(
    tmp_path: Path, capsys: Capture
) -> None:
    write_case_file(tmp_path, "greeting")
    judge = HypothesisJudge(refused_phrases=frozenset({""}))

    exit_code = run_scoring_command(judge, tmp_path)

    assert exit_code == ScoringExitCode.RUN_ERROR
    assert capsys.readouterr().err.endswith(
        "[judge-accuracy] Error: The judge refused every summary of the set\n"
    )


def test_a_failed_check_below_the_confidence_threshold_does_not_count(
    tmp_path: Path, capsys: Capture
) -> None:
    write_case_file(tmp_path, "greeting", FALSE_IMPORT_MISTAKE)

    run_scoring_command(
        HypothesisJudge(_FLAG_FALSE_IMPORT), tmp_path, "--min-confidence", "0.95"
    )

    report = capsys.readouterr().out
    assert "- Min confidence: 0.95. Refused: 0." in report
    assert find_table_row(report, "False statement")[3] == "0/1 (0%)"
    assert find_table_row(report, "0.9")[1] == "1/1 (100%)"
    assert "- `greeting` hunk `app/greet.py#2` (false statement, planted 1)" in report


def test_code_over_the_character_budget_is_scored_apart(
    tmp_path: Path, capsys: Capture
) -> None:
    document = copy_greeting_document()
    long_hunk = document["root_package"]["files"][0]["hunks"][0]
    long_hunk["added_lines"] = [f"line {number} " + "x" * 60 for number in range(60)]
    long_hunk["new_line_count"] = 60
    write_case_file(tmp_path, "greeting", true_document=document)

    run_scoring_command(HypothesisJudge(), tmp_path)

    report = capsys.readouterr().out
    assert find_table_row(report, "hunk, code over the cut")[2] == "0/1 (0%)"
    assert find_table_row(report, "hunk, code within the cut")[2] == "0/2 (0%)"


def test_only_the_texts_a_planted_summary_changes_are_sent_again(
    tmp_path: Path, capsys: Capture
) -> None:
    write_case_file(tmp_path, "greeting", FALSE_IMPORT_MISTAKE)

    run_scoring_command(HypothesisJudge(), tmp_path)

    assert "- Judge requests: 9 sent" in capsys.readouterr().out


class _SilentJudge(HypothesisJudge):
    """Answers no question about a hypothesis that holds ``silent_phrase``."""

    def __init__(self, silent_phrase: str) -> None:
        super().__init__()
        self.silent_phrase = silent_phrase

    async def answer(self, request: JudgeRequest) -> JudgeReply:
        if self.silent_phrase in request.subject.rsplit(HYPOTHESIS_PREFIX, 1)[-1]:
            return build_unreported_reply([])
        return await super().answer(request)


def test_a_summary_the_judge_answers_nothing_about_is_a_refusal(
    tmp_path: Path, capsys: Capture
) -> None:
    write_case_file(tmp_path, "greeting", FALSE_IMPORT_MISTAKE)

    run_scoring_command(_SilentJudge(FALSE_IMPORT_SUMMARY), tmp_path)

    report = capsys.readouterr().out
    assert find_table_row(report, "False statement")[1:4] == ["1", "1", "-"]


def test_the_judge_is_sent_one_request_at_a_time(tmp_path: Path) -> None:
    write_case_file(tmp_path, "greeting", FALSE_IMPORT_MISTAKE)
    judge = CountingJudge()

    run_scoring_command(judge, tmp_path)

    assert judge.most_at_once == 1
