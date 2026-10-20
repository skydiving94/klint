from dataclasses import dataclass, field

from klint.core.models.question_type import QuestionType
from klint.core.models.unit import AuditableUnit

# The unit types a rule is asked about when it names none.
DEFAULT_TARGET_UNIT_TYPES = ("file",)


@dataclass(frozen=True)
class AuditRule:
    rule_id: str
    question_type: QuestionType
    instructions: str
    target_unit_types: list[str] = field(
        default_factory=lambda: list(DEFAULT_TARGET_UNIT_TYPES)
    )
    # Languages the rule is limited to; empty means any language, or none.
    languages: list[str] = field(default_factory=list)
    # Labels for what the rule is about, such as "security".
    tags: list[str] = field(default_factory=list)

    def is_applicable_to(self, unit: AuditableUnit) -> bool:
        if unit.unit_type not in self.target_unit_types:
            return False
        if not self.languages:
            return True
        if unit.language is None:
            return False
        allowed = {language.lower() for language in self.languages}
        return unit.language.lower() in allowed
