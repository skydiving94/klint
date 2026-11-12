"""The code-unit scoring command, run on small case sets with a fake judge."""

from pathlib import Path

import pytest

from judge_accuracy.code_units.length_bands import LENGTH_BANDS
from judge_accuracy.code_units.scoring_command import (
    DEFAULT_CASE_SET,
    ScoringExitCode,
)
from tests.judge_accuracy.code_unit_scoring import (
    SELECT_ALL_PROBLEM,
    SHORT_MODULE,
    MarkerJudge,
    build_long_module,
    run_code_unit_scoring,
    write_case_module,
)
from tests.judge_accuracy.scoring import find_table_row
from tests.support.fakes import FakeJudge

Capture = pytest.CaptureFixture[str]
_FLAG_SELECT_ALL = {"over_fetching_data": "SELECT *"}


@pytest.fixture(autouse=True)
def _private_environment(shell_env: dict[str, str]) -> None:
    del shell_env


def test_a_planted_problem_the_judge_flags_is_caught(
    tmp_path: Path, capsys: Capture
) -> None:
    write_case_module(tmp_path, "users", SHORT_MODULE, SELECT_ALL_PROBLEM)

    exit_code = run_code_unit_scoring(MarkerJudge(_FLAG_SELECT_ALL), tmp_path)

    report = capsys.readouterr().out
    assert exit_code == ScoringExitCode.SCORED
    _, planted, caught, own_check, true, flagged, refused = find_table_row(
        report, "Every length"
    )
    # The function and the file each change, but only the function is asked
    # the rule the problem breaks.
    assert (planted, caught, own_check) == ("1", "1/1 (100%)", "1/1 (100%)")
    assert (flagged, refused) == ("0/2 (0%)", "0")
    assert int(true) == 2


def test_a_planted_problem_the_judge_misses_is_listed(
    tmp_path: Path, capsys: Capture
) -> None:
    write_case_module(tmp_path, "users", SHORT_MODULE, SELECT_ALL_PROBLEM)

    run_code_unit_scoring(MarkerJudge({}), tmp_path)

    report = capsys.readouterr().out
    assert "Planted problems missed (1)" in report
    assert "`users.py::find_user` (#1, over_fetching_data)" in report


def test_every_unit_is_shown_whole(tmp_path: Path, capsys: Capture) -> None:
    write_case_module(tmp_path, "counts", build_long_module())
    judge = FakeJudge()

    run_code_unit_scoring(judge, tmp_path)

    capsys.readouterr()
    longest = max(len(request.subject) for request in judge.requests)
    assert longest > 2 * 2_000
    assert not any("left out to stay within" in r.subject for r in judge.requests)


def test_long_units_are_judged_at_each_band_they_reach(
    tmp_path: Path, capsys: Capture
) -> None:
    write_case_module(tmp_path, "counts", build_long_module(step_count=200))

    run_code_unit_scoring(FakeJudge(), tmp_path)

    report = capsys.readouterr().out
    for band in LENGTH_BANDS[:6]:
        true_count = find_table_row(report, f"{band.describe()} characters")[4]
        assert int(true_count) > 0, band


def test_budget_stops_where_true_units_start_to_be_flagged(
    tmp_path: Path, capsys: Capture
) -> None:
    long_module = build_long_module(step_count=200)
    write_case_module(
        tmp_path,
        "counts",
        long_module,
        {
            "rule_id": "n_plus_1_query",
            "old_text": '    """Return the rows of every table."""\n',
            "new_text": '    """Return the rows of every table."""\n'
            "    for name in names:\n        await database.query(name)\n",
            "why_wrong": "A query per name.",
        },
    )

    run_code_unit_scoring(
        MarkerJudge({"n_plus_1_query": "for name in names"}, "god_component"),
        tmp_path,
    )

    report = capsys.readouterr().out
    _, baseline, budget, stopped_by = find_table_row(report, "0.0")
    assert budget == "2,000"
    assert stopped_by.startswith("2,000 to 2,999: ")
    assert "of true units, above" in stopped_by
    caught, flagged = baseline.split(" / ")
    assert caught.endswith("(100%)")
    assert flagged.endswith("(0%)")


def test_an_old_text_not_in_the_module_is_an_error(
    tmp_path: Path, capsys: Capture
) -> None:
    write_case_module(
        tmp_path, "users", SHORT_MODULE, {**SELECT_ALL_PROBLEM, "old_text": "nowhere"}
    )

    exit_code = run_code_unit_scoring(FakeJudge(), tmp_path)

    assert exit_code == ScoringExitCode.RUN_ERROR
    assert (
        "users.json, planted problem 1: old_text occurs 0 times in users.py, not once"
        in capsys.readouterr().err
    )


def test_a_planted_problem_that_breaks_the_module_is_an_error(
    tmp_path: Path, capsys: Capture
) -> None:
    write_case_module(
        tmp_path, "users", SHORT_MODULE, {**SELECT_ALL_PROBLEM, "new_text": "(("}
    )

    exit_code = run_code_unit_scoring(FakeJudge(), tmp_path)

    assert exit_code == ScoringExitCode.RUN_ERROR
    assert "planted problem 1 is not valid Python" in capsys.readouterr().err


def test_the_repository_set_has_true_and_planted_units_in_every_band(
    in_repo_root: Path, capsys: Capture
) -> None:
    del in_repo_root

    exit_code = run_code_unit_scoring(FakeJudge(), DEFAULT_CASE_SET)

    report = capsys.readouterr().out
    assert exit_code == ScoringExitCode.SCORED
    for band in LENGTH_BANDS:
        row = find_table_row(report, f"{band.describe()} characters")
        assert int(row[1]) >= 15, band
        assert int(row[4]) >= 15, band
