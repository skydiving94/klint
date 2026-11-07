"""The rule selection stage: the rules a run asks about its units."""

from collections.abc import Sequence
from pathlib import Path

from klint.catalog.domain_neutral import does_path_match_glob
from klint.core.interfaces import AuditKind, BaseRuleSource
from klint.core.models.rules import AppliedRuleExclusion, RuleExclusion, RuleSet
from klint.core.models.units import AuditableUnit, UnitTraits


class RuleSelection:
    """Loads the rules of a kind of audit by the traits of the units.

    rule_exclusions are the project's: each turns one rule off for the units
    whose paths its globs match.
    """

    def __init__(self, rule_exclusions: Sequence[RuleExclusion] = ()) -> None:
        self._rule_exclusions = tuple(rule_exclusions)

    async def select_rules(
        self,
        units: Sequence[AuditableUnit],
        audit_kind: AuditKind,
        custom_rule_source: BaseRuleSource | None = None,
    ) -> RuleSet:
        """Return the rule set that chooses the rules to ask about each unit.

        The rules are loaded once for each set of traits among the units.
        The rules of ``custom_rule_source``, when given, merge over the
        loaded ones. Raises when a rule source cannot be used. With no unit,
        the rules are still loaded once, so that such a source stops the
        audit whatever the input holds. An exclusion applies to a unit only
        where its rule would have been asked.
        """
        traits_of_units = list(dict.fromkeys(unit.traits for unit in units)) or [
            UnitTraits()
        ]
        traits_to_rules = {
            traits: await audit_kind.rule_loader.load_rules(traits, custom_rule_source)
            for traits in traits_of_units
        }
        all_rules = RuleSet(traits_to_rules)
        applied_exclusions = [
            applied
            for exclusion in self._rule_exclusions
            if (applied := _apply_exclusion(exclusion, units, all_rules)) is not None
        ]
        return RuleSet(traits_to_rules, applied_exclusions)


def _apply_exclusion(
    exclusion: RuleExclusion, units: Sequence[AuditableUnit], all_rules: RuleSet
) -> AppliedRuleExclusion | None:
    """Return ``exclusion`` with the units it turns its rule off for; None if none."""
    unit_ids = tuple(
        unit.unit_id
        for unit in units
        if _does_exclusion_match(exclusion, unit)
        and any(
            rule.rule_id == exclusion.rule_id
            for rule in all_rules.select_rules_for(unit)
        )
    )
    if not unit_ids:
        return None
    return AppliedRuleExclusion(exclusion=exclusion, unit_ids=unit_ids)


def _does_exclusion_match(exclusion: RuleExclusion, unit: AuditableUnit) -> bool:
    """Return True when one of the exclusion's globs matches the unit's path."""
    location = unit.get_location()
    if location is None:
        return False
    try:
        path_in_project = (
            Path(location.path).resolve().relative_to(exclusion.base_directory)
        )
    except ValueError:
        return False
    return any(does_path_match_glob(path_in_project, glob) for glob in exclusion.paths)
