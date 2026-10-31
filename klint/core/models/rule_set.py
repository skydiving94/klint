"""The rules of one audit run, and which of them each unit is asked."""

from collections.abc import Mapping, Sequence

from klint.core.models.file_traits import FileTraits
from klint.core.models.rule import AuditRule
from klint.core.models.unit import AuditableUnit


class RuleSet:
    """The rules loaded for one run, chosen for each unit it audits.

    traits_to_rules holds, for the traits of the units, the rules loaded
    for units with those traits. A unit is asked those of them that apply to
    it, by unit type and by each trait a rule limits.
    """

    def __init__(
        self, traits_to_rules: Mapping[FileTraits, Sequence[AuditRule]]
    ) -> None:
        self._traits_to_rules = {
            traits: tuple(rules) for traits, rules in traits_to_rules.items()
        }

    def select_rules_for(self, unit: AuditableUnit) -> list[AuditRule]:
        """Return the rules to ask about ``unit``, in load order; may be none."""
        rules = self._traits_to_rules.get(FileTraits(language=unit.language), ())
        return [rule for rule in rules if rule.is_applicable_to(unit)]
