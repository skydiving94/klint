"""Findings and report filtering and ordering."""

from typing import Any

from klint.core.models.location import Location
from klint.core.models.report import AuditFinding, AuditReport
from klint.core.models.scale import Choice
from tests.support.builders import FAIL, IRRELEVANT, LACK_OF_EVIDENCE, PASS


def _finding(
    rule_id: str, choice: Choice, confidence: float | None, unit_id: str = "a.py"
) -> AuditFinding:
    return AuditFinding(
        rule_id=rule_id,
        unit_id=unit_id,
        answer=choice,
        question="?",
        confidence=confidence,
    )


def _report(*findings: AuditFinding) -> AuditReport:
    report = AuditReport()
    for finding in findings:
        report.record(finding)
    return report


def _rule_ids(issues: list[dict[str, Any]]) -> list[str]:
    return [issue["rule_id"] for issue in issues]


def test_report_returns_failures_only_unless_asked_for_all() -> None:
    report = _report(_finding("a", PASS, 0.9), _finding("b", FAIL, 0.9))
    assert _rule_ids(report.get_issues()) == ["b"]
    assert len(report.get_issues(fails_only=False)) == 2


def test_report_filters_by_confidence_but_keeps_unscored_findings() -> None:
    report = _report(
        _finding("low", FAIL, 0.2),
        _finding("high", FAIL, 0.8),
        _finding("unscored", FAIL, None),
    )
    assert _rule_ids(report.get_issues(min_confidence=0.5)) == ["high", "unscored"]


def test_report_orders_by_judgment_then_confidence_then_rule_id() -> None:
    report = _report(
        _finding("p", PASS, 0.9),
        _finding("i", IRRELEVANT, 0.9),
        _finding("f_low", FAIL, 0.3),
        _finding("l", LACK_OF_EVIDENCE, 0.9),
        _finding("f_b", FAIL, 0.7),
        _finding("f_a", FAIL, 0.7),
    )
    order = _rule_ids(report.get_issues(fails_only=False))
    assert order == ["f_a", "f_b", "f_low", "l", "p", "i"]


def test_report_keeps_the_findings_of_each_unit_together_in_unit_order() -> None:
    report = _report(
        _finding("p", PASS, 0.9, unit_id="b.py"),
        _finding("f", FAIL, 0.9, unit_id="b.py"),
        _finding("f", FAIL, 0.5, unit_id="a.py"),
    )

    findings = report.get_findings(fails_only=False)

    assert [(f.unit_id, f.rule_id) for f in findings] == [
        ("b.py", "f"),
        ("b.py", "p"),
        ("a.py", "f"),
    ]


def test_report_lists_the_audited_units_in_recorded_order() -> None:
    report = AuditReport()
    report.record_audited_unit("b.py")
    report.record_audited_unit("a.py")

    assert report.audited_unit_ids() == ["b.py", "a.py"]


def test_finding_dict_has_the_finding_keys_with_the_unit_context_apart() -> None:
    finding = AuditFinding(
        rule_id="r",
        unit_id="a.py",
        answer=LACK_OF_EVIDENCE,
        question="?",
        confidence=0.5,
        tags=("style",),
        location=Location("a.py", 1, 9),
        context={"rule_id": "from the unit"},
    )
    assert finding.convert_to_dict() == {
        "rule_id": "r",
        "unit_id": "a.py",
        "answer": "Lack of Evidence",
        "confidence": 0.5,
        "choice_key_to_probability": None,
        "question": "?",
        "tags": ["style"],
        "location": {"source": "a.py", "start_line": 1, "end_line": 9},
        "evidence_location": None,
        "context": {"rule_id": "from the unit"},
    }


def test_get_findings_returns_the_same_selection_as_objects() -> None:
    report = _report(_finding("a", PASS, 0.9), _finding("b", FAIL, 0.9))
    (finding,) = report.get_findings()
    assert finding.rule_id == "b"
    assert finding.is_failure()
    assert report.get_issues() == [finding.convert_to_dict()]
