"""Findings and report filtering and ordering."""

from typing import Any

from src.core.models.location import Location
from src.core.models.report import AuditFinding, AuditReport
from src.core.models.scale import Choice
from tests.support.builders import FAIL, IRRELEVANT, LACK_OF_EVIDENCE, PASS


def _finding(rule_id: str, choice: Choice, confidence: float | None) -> AuditFinding:
    return AuditFinding(
        rule_id=rule_id,
        unit_id="a.py",
        choice=choice,
        instructions="?",
        confidence=confidence,
        metadata={"file_path": "a.py"},
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


def test_finding_dict_carries_judgment_text_and_unit_metadata() -> None:
    issue = _finding("r", LACK_OF_EVIDENCE, 0.5).to_dict()
    assert issue == {
        "rule_id": "r",
        "unit_id": "a.py",
        "judgment": "Lack of Evidence",
        "confidence": 0.5,
        "probabilities": None,
        "instructions": "?",
        "file_path": "a.py",
    }


def test_get_findings_returns_the_same_selection_as_objects() -> None:
    report = _report(_finding("a", PASS, 0.9), _finding("b", FAIL, 0.9))
    (finding,) = report.get_findings()
    assert finding.rule_id == "b"
    assert finding.is_failure()
    assert report.get_issues() == [finding.to_dict()]


def test_location_is_not_part_of_the_finding_dict() -> None:
    finding = AuditFinding(
        rule_id="r",
        unit_id="a.py",
        choice=FAIL,
        instructions="?",
        location=Location("a.py", 1, 9),
    )
    assert finding.location is not None
    assert finding.location.line_range == (1, 9)
    assert "location" not in finding.to_dict()
