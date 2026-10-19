import asyncio
from collections.abc import Mapping, Sequence
from typing import Any

from injector import inject

from klint.core.interfaces.audit_progress_listener import BaseAuditProgressListener
from klint.core.interfaces.judge import BaseJudge
from klint.core.models.report import AuditFinding, AuditReport
from klint.core.models.rule import AuditRule
from klint.core.models.scale import AnswerScale
from klint.core.models.unit import AuditableUnit

# The most units audited at the same time.
_MAX_CONCURRENT_AUDITS = 8


class Auditor:
    """Audits units and reports what the judge finds.

    Asks the judge the rules that apply to each unit, a limited number of
    units at a time, and turns the answers into findings. A unit whose audit
    fails is left out and the others go on.
    """

    @inject
    def __init__(self, judge: BaseJudge, scale: AnswerScale) -> None:
        self._judge = judge
        self._scale = scale

    async def audit(
        self,
        units: Sequence[AuditableUnit],
        language_to_rules: Mapping[str | None, Sequence[AuditRule]],
        audit_progress_listener: BaseAuditProgressListener | None = None,
    ) -> AuditReport:
        """Audit each unit with the rules for its language; return the report.

        The report holds the units audited without error, and their findings,
        in the order of ``units``. The listener, when given, is told about
        each unit as its audit ends.
        """
        semaphore = asyncio.Semaphore(_MAX_CONCURRENT_AUDITS)

        async def audit_one(unit: AuditableUnit) -> list[AuditFinding] | None:
            """Return the findings on ``unit``; None when its audit fails."""
            async with semaphore:
                try:
                    findings = await self._audit_unit(
                        unit, language_to_rules.get(unit.language, ())
                    )
                except Exception as error:
                    # Whatever went wrong, such as the judge not answering,
                    # only this unit is left out.
                    if audit_progress_listener is not None:
                        audit_progress_listener.report_unit_failed(unit.unit_id, error)
                    return None
            if audit_progress_listener is not None:
                audit_progress_listener.report_unit_audited(unit.unit_id)
            return findings

        unit_findings = await asyncio.gather(*(audit_one(unit) for unit in units))
        report = AuditReport()
        for unit, findings in zip(units, unit_findings, strict=True):
            if findings is None:
                continue
            report.record_audited_unit(unit.unit_id)
            for finding in findings:
                report.record(finding)
        return report

    async def _audit_unit(
        self, unit: AuditableUnit, rules: Sequence[AuditRule]
    ) -> list[AuditFinding]:
        """Ask the judge the rules that apply to one unit; none means no call."""
        applicable_rules = [r for r in rules if r.is_applicable_to(unit)]
        if not applicable_rules:
            return []
        answers = await self._judge.answer(
            unit.get_content(), self._build_questions(applicable_rules)
        )
        findings: list[AuditFinding] = []
        for rule in applicable_rules:
            answer = answers.get(rule.rule_id, {})
            choice_key = answer.get("choice")
            if choice_key is None:
                continue
            findings.append(
                AuditFinding(
                    rule_id=rule.rule_id,
                    unit_id=unit.unit_id,
                    choice=self._scale.choice(choice_key),
                    instructions=rule.instructions,
                    confidence=answer.get("confidence"),
                    probabilities=answer.get("probabilities"),
                    location=unit.get_location(),
                    metadata=unit.get_metadata(),
                )
            )
        return findings

    def _build_questions(self, rules: Sequence[AuditRule]) -> dict[str, Any]:
        criteria = self._scale.criteria_payload()
        return {
            rule.rule_id: {
                "type": rule.question_type.value,
                "instructions": rule.instructions,
                "criteria": criteria,
            }
            for rule in rules
        }
