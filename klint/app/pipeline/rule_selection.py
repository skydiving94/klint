"""The rule selection stage: the rules a run asks about its units."""

from collections.abc import Sequence
from pathlib import Path

from klint.core.models.audit_kind import AuditKind
from klint.core.models.rule_set import RuleSet
from klint.core.models.unit import AuditableUnit
from klint.core.models.unit_traits import UnitTraits


class RuleSelection:
    """Loads the rules of a kind of audit by the traits of the units."""

    async def select_rules(
        self,
        units: Sequence[AuditableUnit],
        audit_kind: AuditKind,
        custom_rules_source: Path | None = None,
    ) -> RuleSet:
        """Return the rule set that chooses the rules to ask about each unit.

        The rules are loaded once for each set of traits among the units.
        The rules in ``custom_rules_source``, when given, merge over the
        loaded ones. Raises when a rules file cannot be used. With no unit,
        the rules are still loaded once, so that such a file stops the audit
        whatever the input holds.
        """
        traits_of_units = list(dict.fromkeys(unit.traits for unit in units)) or [
            UnitTraits()
        ]
        return RuleSet(
            {
                traits: await audit_kind.rule_loader.load_rules(
                    traits, custom_rules_source
                )
                for traits in traits_of_units
            }
        )
