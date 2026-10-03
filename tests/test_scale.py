"""Answer scales, and the default pass/fail scale sent to the judge."""

import pytest

from src.catalog.common.scales.pass_fail import PASS_FAIL_SCALE
from src.core.models.location import Location
from src.core.models.scale import AnswerScale, Choice

EXPECTED_CRITERIA = {
    "pass": "The provided code or project structure follows the described practice.",
    "fail": "The provided code or project structure violates the described practice.",
    "irrelevant": (
        "The described practice does not apply to this specific code or directory."
    ),
    "lack_of_evidence": (
        "There is not enough information in the provided context to determine "
        "pass, fail, or irrelevance."
    ),
}


def test_default_scale_sends_these_criteria_to_the_judge_in_this_order() -> None:
    payload = PASS_FAIL_SCALE.criteria_payload()
    assert list(payload.items()) == list(EXPECTED_CRITERIA.items())


def test_default_scale_labels_findings_and_report_order() -> None:
    summary = [
        (choice.label, choice.is_finding, choice.priority)
        for choice in PASS_FAIL_SCALE.choices
    ]
    assert summary == [
        ("Pass", False, 2),
        ("Fail", True, 0),
        ("Irrelevant", False, 3),
        ("Lack of Evidence", False, 1),
    ]


def test_choice_lookup_ignores_case_and_rejects_unknown_keys() -> None:
    assert PASS_FAIL_SCALE.choice("FAIL") is PASS_FAIL_SCALE.choice("fail")
    with pytest.raises(KeyError, match="maybe"):
        PASS_FAIL_SCALE.choice("maybe")


def test_a_suite_can_define_its_own_scale() -> None:
    rubric = AnswerScale(
        name="rubric",
        choices=(
            Choice("strong", "Strong", "The essay argues its thesis clearly."),
            Choice("weak", "Weak", "The essay does not.", is_finding=True),
        ),
    )
    assert list(rubric.criteria_payload()) == ["strong", "weak"]
    assert rubric.choice("weak").is_finding


def test_location_line_range_needs_both_lines() -> None:
    assert Location("a.py", 1, 9).line_range == (1, 9)
    assert Location("a.py", 1).line_range is None
    assert Location("pkg").line_range is None
