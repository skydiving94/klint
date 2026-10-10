from abc import ABC, abstractmethod
from pathlib import Path

from src.core.models.unit import AuditableUnit


class BaseUnitExtractor(ABC):
    @abstractmethod
    async def extract(self, target: str | Path) -> list[AuditableUnit]:
        pass
