"""One file, class or function of the set, and what the judge found in it."""

from dataclasses import dataclass
from enum import StrEnum

from judge_accuracy.code_units.case_set import PlantedProblem
from klint.core.models.reports import AuditFinding


class CodeUnitType(StrEnum):
    """The kinds of unit the set scores, named as klint's rules name them."""

    FILE = "file"
    CLASS = "class"
    FUNCTION = "function"


@dataclass(frozen=True)
class JudgedUnit:
    """A true or planted unit, its length shown whole, and the judge's findings.

    unit_name is where the unit sits in its case module, as in
    "orders.py::OrderRepository.find". planted_problem is None for a true
    unit; planted_number counts the module's planted problems from 1.
    findings is None when the judge refused to answer about the unit.
    """

    case_module_name: str
    unit_name: str
    unit_type: CodeUnitType
    length: int
    findings: tuple[AuditFinding, ...] | None
    planted_problem: PlantedProblem | None = None
    planted_number: int | None = None

    def is_true(self) -> bool:
        return self.planted_problem is None

    def is_refused(self) -> bool:
        return self.findings is None

    def is_flagged(self, min_confidence: float) -> bool:
        """Return True when a check failed on the unit with ``min_confidence``."""
        return bool(self.list_failed_rule_ids(min_confidence))

    def is_caught_by_own_check(self, min_confidence: float) -> bool:
        """Return True when the rule the planted problem breaks failed."""
        return (
            self.planted_problem is not None
            and self.planted_problem.rule_id
            in self.list_failed_rule_ids(min_confidence)
        )

    def list_failed_rule_ids(self, min_confidence: float) -> list[str]:
        """Return the rules that failed on the unit with ``min_confidence``."""
        return [
            finding.rule_id
            for finding in self.findings or ()
            if finding.is_problem() and finding.does_meet_confidence(min_confidence)
        ]

    def describe_failures(self) -> str:
        """Return each failed rule and its confidence, as "rule 0.42"."""
        return ", ".join(
            f"{finding.rule_id} {finding.confidence or 0.0:.2f}"
            for finding in self.findings or ()
            if finding.is_problem()
        )
