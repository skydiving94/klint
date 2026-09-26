import asyncio
from typing import Any
from src.core.domain.models import AuditReport
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

        tasks = [
            self._evaluator.evaluate(unit, rule)
            for unit in units
            for rule in rules
            if rule.is_applicable_to(unit)
        ]
        for finding in await asyncio.gather(*tasks):
            report.record(finding)

        return report
