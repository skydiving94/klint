"""A rule pack as a rule source reads it, before its rules are built."""

from collections.abc import Sequence
from dataclasses import dataclass
from enum import Enum, auto

from klint.core.models.question_type import QuestionType


@dataclass(frozen=True)
class PackScope:
    """The units a pack is for, as its header states them.

    languages is None when the pack is not limited to some languages, as for
    a file without a header.
    """

    languages: tuple[str, ...] | None = None

    def matches(self, language: str) -> bool:
        """Return True when the pack is for units written in ``language``."""
        return self.languages is None or language.lower() in self._lowered_languages()

    def narrow(self, rule_languages: Sequence[str]) -> list[str]:
        """Return the languages a rule of this pack is limited to.

        A rule that names no language inherits the pack's; one that does
        keeps those that are also the pack's.
        """
        if self.languages is None:
            return list(rule_languages)
        if not rule_languages:
            return list(self.languages)
        return [
            language
            for language in rule_languages
            if language.lower() in self._lowered_languages()
        ]

    def _lowered_languages(self) -> set[str]:
        return {language.lower() for language in self.languages or ()}


@dataclass(frozen=True)
class RuleSpec:
    """One rule as its file writes it.

    target_unit_types is the default when the rule names none. languages
    are the rule's own, before its pack's header narrows them; empty when
    it names none.
    """

    rule_id: str
    question_type: QuestionType
    instructions: str
    target_unit_types: tuple[str, ...]
    languages: tuple[str, ...]
    tags: tuple[str, ...]


class RuleProblemSeverity(Enum):
    """What a problem in a rule does to the load."""

    # The rule, or the field, is ignored and the load goes on.
    WARNING = auto()
    # The load stops.
    ERROR = auto()


@dataclass(frozen=True)
class RuleProblem:
    """A problem found in one rule, with a message naming the rule and the file."""

    severity: RuleProblemSeverity
    message: str


@dataclass(frozen=True)
class RulePackSpec:
    """One rule pack as read: where it is from, the units it is for, its rules.

    origin names where the pack was read from in messages, such as the path
    of its file. rule_problems are the problems found in the rules, in file order. They
    are kept rather than reported, so that a pack is reported on only when
    it is used. A rule with an ERROR problem is not among rules.
    """

    origin: str
    scope: PackScope
    rules: tuple[RuleSpec, ...]
    rule_problems: tuple[RuleProblem, ...]
