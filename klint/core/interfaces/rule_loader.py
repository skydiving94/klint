from abc import ABC, abstractmethod
from pathlib import Path

from klint.core.models.rule import AuditRule
from klint.core.models.unit_traits import UnitTraits


class BaseRuleLoader(ABC):
    @abstractmethod
    async def load_rules(
        self, traits: UnitTraits, custom_rules_source: str | Path | None = None
    ) -> list[AuditRule]:
        """Return the rules to ask about files with ``traits``.

        The rules in ``custom_rules_source``, when given, merge over them by
        rule ID.
        """
