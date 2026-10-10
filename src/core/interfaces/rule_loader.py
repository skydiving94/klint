from abc import ABC, abstractmethod
from typing import Any

from src.core.models.rule import AuditRule


class BaseRuleLoader(ABC):
    @abstractmethod
    async def load_rules(self, custom_rules_source: Any = None) -> list[AuditRule]:
        pass
