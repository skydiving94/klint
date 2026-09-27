from dataclasses import dataclass, field
from typing import List

from src.core.domain.enums import QuestionType
from src.core.domain.units import AuditableUnit


@dataclass(frozen=True)
class AuditRule:
    rule_id: str
    question_type: QuestionType
    instructions: str
    target_unit_types: List[str] = field(
        default_factory=AuditableUnit.known_unit_types)

    def is_applicable_to(self, unit: AuditableUnit) -> bool:
        return unit.unit_type in self.target_unit_types
