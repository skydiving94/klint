from abc import ABC, abstractmethod

from klint.core.interfaces.rule_source import BaseRuleSource
from klint.core.models.rules import AuditRule, RulePackSpec
from klint.core.models.units import UnitTraits


class BaseRuleLoader(ABC):
    @abstractmethod
    async def load_rules(
        self, traits: UnitTraits, custom_rule_source: BaseRuleSource | None = None
    ) -> list[AuditRule]:
        """Return the rules to ask about units with ``traits``.

        The rules in ``custom_rule_source``, when given, merge over them by
        rule ID.
        """

    @abstractmethod
    def read_rule_packs(self) -> list[RulePackSpec]:
        """Return every pack the loader may draw rules from, as its sources read them.

        A pack whose rules are never loaded for any unit is listed too, so
        that a rule can be looked up by its ID whatever it applies to.
        """
