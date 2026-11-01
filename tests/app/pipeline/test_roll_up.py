"""Roll-up statuses: what the problems on nested units say about their holders."""

import pytest

from klint.core.models.roll_up_status import RollUpStatus
from tests.support.fakes import SubjectJudge
from tests.support.outline_suite import run_outline_audit

NO, OWN, DESCENDANT = (
    RollUpStatus.NO_PROBLEM,
    RollUpStatus.OWN_PROBLEM,
    RollUpStatus.DESCENDANT_PROBLEM,
)


def test_failing_leaf_gives_every_ancestor_a_descendant_problem() -> None:
    outcome = run_outline_audit(SubjectJudge({"Section 1.1.": "fail"}))

    assert outcome.report.map_unit_id_to_roll_up_status() == {
        "book": DESCENDANT,
        "chapter 1": DESCENDANT,
        "section 1.1": OWN,
        "section 1.2": NO,
        "chapter 2": NO,
        "section 2.1": NO,
    }


def test_own_problem_wins_over_a_descendant_problem() -> None:
    judge = SubjectJudge({"Section 1.1.": "fail", "Chapter 1.": "fail"})

    outcome = run_outline_audit(judge)

    assert outcome.report.find_roll_up_status("chapter 1") is OWN
    assert outcome.report.find_roll_up_status("book") is DESCENDANT


def test_problem_rolls_up_past_a_unit_whose_audit_failed() -> None:
    judge = SubjectJudge(
        {"Section 1.1.": "fail"}, refused_subjects=frozenset({"Chapter 1."})
    )

    outcome = run_outline_audit(judge)

    report = outcome.report
    assert "chapter 1" not in report.map_unit_id_to_roll_up_status()
    assert report.find_parent_unit_id("section 1.1") == "chapter 1"
    assert report.find_roll_up_status("book") is DESCENDANT
    with pytest.raises(ValueError, match=r"No roll-up status .* 'chapter 1'"):
        report.find_roll_up_status("chapter 1")


def test_problem_below_the_least_confidence_asked_for_does_not_roll_up() -> None:
    judge = SubjectJudge({"Section 1.1.": "fail"}, confidence=0.4)

    outcome = run_outline_audit(judge, min_confidence=0.5)

    assert set(outcome.report.map_unit_id_to_roll_up_status().values()) == {NO}


def test_answers_that_are_not_problems_give_no_problem() -> None:
    judge = SubjectJudge({"Section 1.1.": "lack_of_evidence"})

    outcome = run_outline_audit(judge)

    assert set(outcome.report.map_unit_id_to_roll_up_status().values()) == {NO}
