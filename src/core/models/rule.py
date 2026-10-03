from dataclasses import dataclass, field
from typing import List

from src.core.models.question_type import QuestionType
from src.core.models.unit import AuditableUnit


@dataclass(frozen=True)
class AuditRule:
    rule_id: str
    question_type: QuestionType
    instructions: str
    target_unit_types: List[str] = field(default_factory=lambda: ["file"])
    # Languages the rule is limited to; empty means any language, or none.
    languages: List[str] = field(default_factory=list)
    # Labels for what the rule is about, such as "security".
    tags: List[str] = field(default_factory=list)

    def is_applicable_to(self, unit: AuditableUnit) -> bool:
        if unit.unit_type not in self.target_unit_types:
            return False
        if not self.languages:
            return True
        if unit.language is None:
            return False
        allowed = {language.lower() for language in self.languages}
        return unit.language.lower() in allowed
