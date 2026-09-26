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

    def run_audit(self, target: Any, custom_rules_source: Any = None) -> AuditReport:
        units = self._extractor.extract(target)
        rules = self._rule_loader.load_rules(custom_rules_source)
        report = AuditReport()

        for unit in units:
            for rule in rules:
                if rule.is_applicable_to(unit):
                    finding = self._evaluator.evaluate(unit, rule)
                    report.record(finding)

        return report
