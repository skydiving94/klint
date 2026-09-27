from abc import ABC, abstractmethod
from typing import Any, List

from src.core.domain.rule import AuditRule


class BaseRuleLoader(ABC):
    @abstractmethod
    async def load_rules(self, custom_rules_source: Any = None) -> List[AuditRule]:
        pass
