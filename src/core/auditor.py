import asyncio
from typing import Any, Dict, List, Sequence

from src.core.interfaces.evaluator import BaseKevEvaluator
from src.core.interfaces.extractor import BaseUnitExtractor
from src.core.interfaces.rule_loader import BaseRuleLoader
from src.core.models.report import AuditFinding, AuditReport
from src.core.models.rule import AuditRule
from src.core.models.scale import AnswerScale
from src.core.models.unit import AuditableUnit


class AuditService:
    def __init__(
        self,
        extractor: BaseUnitExtractor,
        evaluator: BaseKevEvaluator,
        rule_loader: BaseRuleLoader,
        scale: AnswerScale,
    ):
        self._extractor = extractor
        self._evaluator = evaluator
        self._rule_loader = rule_loader
        self._scale = scale

    async def run_audit(self, target: Any, custom_rules_source: Any = None) -> AuditReport:
        units, rules = await asyncio.gather(
            self._extractor.extract(target),
            self._rule_loader.load_rules(custom_rules_source),
        )

        report = AuditReport()
        tasks = []

        for unit in units:
            applicable_rules = [r for r in rules if r.is_applicable_to(unit)]
            if applicable_rules:
                tasks.append(self._evaluate(unit, applicable_rules))

        for unit_findings in await asyncio.gather(*tasks):
            for finding in unit_findings:
                report.record(finding)

        return report

    async def _evaluate(
        self, unit: AuditableUnit, rules: Sequence[AuditRule]
    ) -> List[AuditFinding]:
        """Ask the judge every rule about one unit and turn the answers into findings."""
        answers = await self._evaluator.answer(
            unit.get_content(), self._build_questions(rules)
        )
        findings: List[AuditFinding] = []
        for rule in rules:
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

    def _build_questions(self, rules: Sequence[AuditRule]) -> Dict[str, Any]:
        criteria = self._scale.criteria_payload()
        return {
            rule.rule_id: {
                "type": rule.question_type.value,
                "instructions": rule.instructions,
                "criteria": criteria,
            }
            for rule in rules
        }
