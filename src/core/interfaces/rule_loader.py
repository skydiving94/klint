from abc import ABC, abstractmethod
from pathlib import Path

from src.core.models.file_traits import FileTraits
from src.core.models.rule import AuditRule


class BaseRuleLoader(ABC):
    @abstractmethod
    async def load_rules(
        self, traits: FileTraits, custom_rules_source: str | Path | None = None
    ) -> list[AuditRule]:
        """Return the rules to ask about files with ``traits``.

        The rules in ``custom_rules_source``, when given, merge over them by
        rule ID.
        """
