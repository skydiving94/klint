from abc import ABC, abstractmethod
from typing import List, Sequence

from src.core.models.report import AuditFinding
from src.core.models.rule import AuditRule
from src.core.models.unit import AuditableUnit


class BaseKevEvaluator(ABC):
    @abstractmethod
    async def evaluate(
        self, unit: AuditableUnit, rules: Sequence[AuditRule]
    ) -> List[AuditFinding]:
        pass
