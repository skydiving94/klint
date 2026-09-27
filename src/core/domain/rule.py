from dataclasses import dataclass, field
from typing import Dict, List

from src.core.domain.enums import QuestionType, UnitType
from src.core.domain.units.base import AuditableUnit


@dataclass(frozen=True)
class AuditRule:
    rule_id: str
    question_type: QuestionType
    instructions: str
    criteria: Dict[str, str]
    target_unit_types: List[UnitType] = field(
        default_factory=lambda: list(UnitType)
    )

    def is_applicable_to(self, unit: AuditableUnit) -> bool:
        return unit.unit_type in self.target_unit_types
