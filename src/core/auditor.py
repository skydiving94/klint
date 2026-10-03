import asyncio
from typing import Any

from src.core.models.report import AuditReport
from src.core.interfaces.evaluator import BaseKevEvaluator
from src.core.interfaces.extractor import BaseUnitExtractor
from src.core.interfaces.rule_loader import BaseRuleLoader


class AuditService:
    def __init__(
        self,
        extractor: BaseUnitExtractor,
        evaluator: BaseKevEvaluator,
        rule_loader: BaseRuleLoader,
    ):
        self._extractor = extractor
        self._evaluator = evaluator
        self._rule_loader = rule_loader

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
                tasks.append(self._evaluator.evaluate(unit, applicable_rules))

        for unit_findings in await asyncio.gather(*tasks):
            for finding in unit_findings:
                report.record(finding)

        return report
