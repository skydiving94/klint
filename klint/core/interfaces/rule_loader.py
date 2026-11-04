from abc import ABC, abstractmethod

from klint.core.interfaces.rule_source import BaseRuleSource
from klint.core.models.rules.rule import AuditRule
from klint.core.models.units.unit_traits import UnitTraits


class BaseRuleLoader(ABC):
    @abstractmethod
    async def load_rules(
        self, traits: UnitTraits, custom_rule_source: BaseRuleSource | None = None
    ) -> list[AuditRule]:
        """Return the rules to ask about units with ``traits``.

        The rules in ``custom_rule_source``, when given, merge over them by
        rule ID.
        """
