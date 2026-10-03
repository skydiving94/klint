"""Judgments, findings and report filtering and ordering."""

from typing import Any

from src.core.models.judgment import Judgment
from src.core.models.report import AuditFinding, AuditReport


def test_judgment_criteria_cover_the_four_choices() -> None:
    assert set(Judgment.as_criteria_payload()) == {
        "pass",
        "fail",
        "irrelevant",
        "lack_of_evidence",
    }


def _finding(
    rule_id: str, judgment: Judgment, confidence: float | None
) -> AuditFinding:
    return AuditFinding(
        rule_id=rule_id,
        unit_id="a.py",
        judgment=judgment,
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
    report = _report(
        _finding("a", Judgment.PASS, 0.9), _finding("b", Judgment.FAIL, 0.9)
    )
    assert _rule_ids(report.get_issues()) == ["b"]
    assert len(report.get_issues(fails_only=False)) == 2


def test_report_filters_by_confidence_but_keeps_unscored_findings() -> None:
    report = _report(
        _finding("low", Judgment.FAIL, 0.2),
        _finding("high", Judgment.FAIL, 0.8),
        _finding("unscored", Judgment.FAIL, None),
    )
    assert _rule_ids(report.get_issues(min_confidence=0.5)) == ["high", "unscored"]


def test_report_orders_by_judgment_then_confidence_then_rule_id() -> None:
    report = _report(
        _finding("p", Judgment.PASS, 0.9),
        _finding("i", Judgment.IRRELEVANT, 0.9),
        _finding("f_low", Judgment.FAIL, 0.3),
        _finding("l", Judgment.LACK_OF_EVIDENCE, 0.9),
        _finding("f_b", Judgment.FAIL, 0.7),
        _finding("f_a", Judgment.FAIL, 0.7),
    )
    order = _rule_ids(report.get_issues(fails_only=False))
    assert order == ["f_a", "f_b", "f_low", "l", "p", "i"]


def test_finding_dict_carries_judgment_text_and_unit_metadata() -> None:
    issue = _finding("r", Judgment.LACK_OF_EVIDENCE, 0.5).to_dict()
    assert issue == {
        "rule_id": "r",
        "unit_id": "a.py",
        "judgment": "Lack of Evidence",
        "confidence": 0.5,
        "probabilities": None,
        "instructions": "?",
        "file_path": "a.py",
    }
