from abc import ABC, abstractmethod
from typing import Any

from src.core.models.unit import AuditableUnit


class BaseUnitExtractor(ABC):
    @abstractmethod
    async def extract(self, target: Any) -> list[AuditableUnit]:
        pass
