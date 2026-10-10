import asyncio
from collections.abc import Iterator, Sequence
from pathlib import Path
from typing import Any

from src.core.interfaces.extractor import BaseUnitExtractor
from src.core.interfaces.judge import BaseJudge
from src.core.interfaces.rule_loader import BaseRuleLoader
from src.core.models.report import AuditFinding, AuditReport
from src.core.models.rule import AuditRule
from src.core.models.scale import AnswerScale
from src.core.models.unit import AuditableUnit


class Auditor:
    """Audits a target and reports what the judge finds.

    Extracts units from the target, asks the judge the rules that apply to
    each one, and turns the answers into findings.
    """

    def __init__(
        self,
        extractor: BaseUnitExtractor,
        judge: BaseJudge,
        rule_loader: BaseRuleLoader,
        scale: AnswerScale,
    ) -> None:
        self._extractor = extractor
        self._judge = judge
        self._rule_loader = rule_loader
        self._scale = scale

    async def load_rules(
        self, custom_rules_source: str | Path | None = None
    ) -> list[AuditRule]:
        return await self._rule_loader.load_rules(custom_rules_source)

    async def extract_units(
        self, target: str | Path, walk_children: bool = False
    ) -> list[AuditableUnit]:
        """Return the target's units.

        With walk_children, every unit nested inside them is returned as well,
        parents before children.
        """
        units = await self._extractor.extract(target)
        if not walk_children:
            return list(units)
        return [nested for unit in units for nested in self._walk(unit)]

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

    async def run_audit(
        self,
        target: str | Path,
        custom_rules_source: str | Path | None = None,
        walk_children: bool = False,
    ) -> AuditReport:
        units, rules = await asyncio.gather(
            self.extract_units(target, walk_children),
            self.load_rules(custom_rules_source),
        )
        report = AuditReport()
        results = await asyncio.gather(
            *(self.audit_unit(unit, rules) for unit in units)
        )
        for unit_findings in results:
            for finding in unit_findings:
                report.record(finding)
        return report

    def _walk(self, unit: AuditableUnit) -> Iterator[AuditableUnit]:
        yield unit
        for child in unit.children():
            yield from self._walk(child)

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
