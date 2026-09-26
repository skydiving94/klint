from abc import ABC, abstractmethod
from src.core.domain.models import AuditableUnit, AuditFinding, AuditRule


class BaseKevEvaluator(ABC):
    @abstractmethod
    def evaluate(self, unit: AuditableUnit, rule: AuditRule) -> AuditFinding:
        pass
