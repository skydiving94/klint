from dataclasses import dataclass, field
from typing import List

from src.core.models.question_type import QuestionType
from src.core.models.units import AuditableUnit


@dataclass(frozen=True)
class AuditRule:
    rule_id: str
    question_type: QuestionType
    instructions: str
    target_unit_types: List[str] = field(default_factory=lambda: ["file"])

    def is_applicable_to(self, unit: AuditableUnit) -> bool:
        return unit.unit_type in self.target_unit_types
