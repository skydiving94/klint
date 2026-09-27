from abc import ABC, abstractmethod
from typing import List, Sequence
from src.core.domain.models import AuditableUnit, AuditFinding, AuditRule


class BaseKevEvaluator(ABC):
    @abstractmethod
    async def evaluate(
        self, unit: AuditableUnit, rules: Sequence[AuditRule]
    ) -> List[AuditFinding]:
        pass
