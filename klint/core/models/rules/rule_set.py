"""The rules of one audit run, and which of them each unit is asked."""

from collections.abc import Mapping, Sequence

from klint.core.models.rules.rule import AuditRule
from klint.core.models.rules.rule_exclusion import AppliedRuleExclusion
from klint.core.models.units import AuditableUnit, UnitTraits


class RuleSet:
    """The rules loaded for one run, chosen for each unit it audits.

    traits_to_rules holds, for the traits of the units, the rules loaded
    for units with those traits. A unit is asked those of them that apply to
    it, by unit type and by each trait a rule limits, except the rules an
    applied exclusion turns off for it.
    """

    def __init__(
        self,
        traits_to_rules: Mapping[UnitTraits, Sequence[AuditRule]],
        applied_rule_exclusions: Sequence[AppliedRuleExclusion] = (),
    ) -> None:
        self._traits_to_rules = {
            traits: tuple(rules) for traits, rules in traits_to_rules.items()
        }
        self._applied_rule_exclusions = tuple(applied_rule_exclusions)
        self._unit_id_to_excluded_rule_ids: dict[str, set[str]] = {}
        for applied in self._applied_rule_exclusions:
            for unit_id in applied.unit_ids:
                self._unit_id_to_excluded_rule_ids.setdefault(unit_id, set()).add(
                    applied.exclusion.rule_id
                )

    def select_rules_for(self, unit: AuditableUnit) -> list[AuditRule]:
        """Return the rules to ask about ``unit``, in load order; may be none."""
        excluded_rule_ids = self._unit_id_to_excluded_rule_ids.get(unit.unit_id, set())
        return [
            rule
            for rule in self._traits_to_rules.get(unit.traits, ())
            if rule.is_applicable_to(unit) and rule.rule_id not in excluded_rule_ids
        ]

    def list_applied_rule_exclusions(self) -> tuple[AppliedRuleExclusion, ...]:
        """Return the exclusions that kept a rule from a unit, in project order."""
        return self._applied_rule_exclusions
