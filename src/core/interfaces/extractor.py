from abc import ABC, abstractmethod
from typing import Any, List
from src.core.domain.models import AuditableUnit


class BaseUnitExtractor(ABC):
    @abstractmethod
    def extract(self, target: Any) -> List[AuditableUnit]:
        pass
