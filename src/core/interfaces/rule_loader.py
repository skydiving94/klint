from abc import ABC, abstractmethod
from pathlib import Path

from src.core.models.rule import AuditRule


class BaseRuleLoader(ABC):
    @abstractmethod
    async def load_rules(
        self, custom_rules_source: str | Path | None = None
    ) -> list[AuditRule]:
        pass
