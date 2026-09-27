from abc import ABC, abstractmethod
from typing import List, Sequence

from src.core.domain.report import AuditFinding
from src.core.domain.rule import AuditRule
from src.core.domain.units import AuditableUnit


class BaseKevEvaluator(ABC):
    @abstractmethod
    async def evaluate(
        self, unit: AuditableUnit, rules: Sequence[AuditRule]
    ) -> List[AuditFinding]:
        pass
