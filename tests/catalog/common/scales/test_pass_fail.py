"""The default pass/fail scale sent to the judge."""

from klint.catalog.common.scales.pass_fail import PASS_FAIL_SCALE

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


def test_default_scale_labels_its_choices_and_counts_only_fail_as_a_finding() -> None:
    # The order of these in a report is checked through AuditReport.
    summary = [(choice.label, choice.is_finding) for choice in PASS_FAIL_SCALE.choices]
    assert summary == [
        ("Pass", False),
        ("Fail", True),
        ("Irrelevant", False),
        ("Lack of Evidence", False),
    ]
