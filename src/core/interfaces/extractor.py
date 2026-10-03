from abc import ABC, abstractmethod
from typing import Any, List

from src.core.models.unit import AuditableUnit


class BaseUnitExtractor(ABC):
    @abstractmethod
    async def extract(self, target: Any) -> List[AuditableUnit]:
        pass
