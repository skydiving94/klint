from collections.abc import Sequence
from typing import Any

from src.core.interfaces.judge import BaseJudge
from src.core.models.report import AuditFinding
from src.core.models.rule import AuditRule
from src.core.models.scale import AnswerScale
from src.core.models.unit import AuditableUnit


class Auditor:
    """Audits units and reports what the judge finds.

    Asks the judge the rules that apply to each unit, and turns the answers
    into findings.
    """

    def __init__(self, judge: BaseJudge, scale: AnswerScale) -> None:
        self._judge = judge
        self._scale = scale

    async def audit_unit(
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
