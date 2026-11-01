"""What a report selects, and the JSON form of a finding."""

from dataclasses import dataclass

from klint.core.models.location import Location
from klint.core.models.report import AuditFinding, AuditReport
from klint.core.models.scale import AnswerChoice
from klint.core.models.unit import UnitContext
from tests.support.builders import FAIL, LACK_OF_EVIDENCE, PASS


@dataclass(frozen=True)
class _ContextWithRuleId(UnitContext):
    rule_id: str


def _finding(
    rule_id: str, answer: AnswerChoice, confidence: float | None, unit_id: str = "a.py"
) -> AuditFinding:
    return AuditFinding(
        rule_id=rule_id,
        unit_id=unit_id,
        answer=answer,
        question="?",
        confidence=confidence,
    )


def _report(*findings: AuditFinding) -> AuditReport:
    report = AuditReport()
    for finding in findings:
        report.record(finding)
    return report


def _rule_ids(findings: list[AuditFinding]) -> list[str]:
    return [finding.rule_id for finding in findings]


def test_report_selects_problems_only_unless_asked_for_every_answer() -> None:
    report = _report(_finding("a", PASS, 0.9), _finding("b", FAIL, 0.9))

    assert _rule_ids(report.select_findings()) == ["b"]
    assert _rule_ids(report.select_findings(should_include_non_problems=True)) == [
        "a",
        "b",
    ]


def test_report_selects_by_confidence_but_keeps_unscored_findings() -> None:
    report = _report(
        _finding("low", FAIL, 0.2),
        _finding("high", FAIL, 0.8),
        _finding("unscored", FAIL, None),
    )

    assert _rule_ids(report.select_findings(min_confidence=0.5)) == [
        "high",
        "unscored",
    ]


def test_report_keeps_the_recorded_order_of_findings_and_audited_units() -> None:
    report = _report(_finding("z", FAIL, 0.1), _finding("a", FAIL, 0.9))
    report.record_audited_unit("b.py")
    report.record_audited_unit("a.py")

    assert _rule_ids(report.select_findings()) == ["z", "a"]
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
        context=_ContextWithRuleId(rule_id="from the unit"),
    )

    assert finding.convert_to_dict() == {
        "rule_id": "r",
        "unit_id": "a.py",
        "answer": "Lack of Evidence",
        "confidence": 0.5,
        "choice_key_to_probability": None,
        "question": "?",
        "tags": ["style"],
        "location": {"path": "a.py", "start_line": 1, "end_line": 9},
        "evidence_location": None,
        "context": {"rule_id": "from the unit"},
    }
