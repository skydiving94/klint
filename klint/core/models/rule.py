from dataclasses import dataclass, field

from klint.core.models.question_type import QuestionType
from klint.core.models.unit import AuditableUnit

# The unit types a rule is asked about when it names none.
DEFAULT_TARGET_UNIT_TYPES = ("file",)


@dataclass(frozen=True)
class AuditRule:
    rule_id: str
    question_type: QuestionType
    question: str
    target_unit_types: list[str] = field(
        default_factory=lambda: list(DEFAULT_TARGET_UNIT_TYPES)
    )
    # Languages the rule is limited to; empty means any language, or none.
    languages: list[str] = field(default_factory=list)
    # Labels for what the rule is about, such as "security".
    tags: list[str] = field(default_factory=list)
    # Unit tags the rule is limited to, such as "backend"; empty means any.
    unit_tags: list[str] = field(default_factory=list)

    def is_applicable_to(self, unit: AuditableUnit) -> bool:
        """Return True when the rule is asked about ``unit``.

        The rule must target the unit's type, and the unit's language must be
        one of the rule's languages, when it names some. A rule limited to
        unit tags applies to a unit with any of them, and to a unit with no
        tags at all, since nothing tells which side such a unit belongs to.
        """
        if unit.unit_type not in self.target_unit_types:
            return False
        return self._is_language_allowed(unit.traits.language) and (
            self._are_tags_allowed(unit.traits.tags)
        )

    def _is_language_allowed(self, language: str | None) -> bool:
        if not self.languages:
            return True
        if language is None:
            return False
        allowed = {rule_language.lower() for rule_language in self.languages}
        return language.lower() in allowed

    def _are_tags_allowed(self, unit_tags: frozenset[str]) -> bool:
        if not self.unit_tags or not unit_tags:
            return True
        allowed = {rule_unit_tag.lower() for rule_unit_tag in self.unit_tags}
        return bool(allowed & {unit_tag.lower() for unit_tag in unit_tags})
