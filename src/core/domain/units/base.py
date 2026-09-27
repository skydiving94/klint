from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict

from src.core.domain.enums import UnitType


@dataclass(frozen=True)
class AuditableUnit(ABC):
    """Abstract base node for any auditable code or project structure unit.

    Composite subclasses (e.g. project directories, Python modules, classes)
    act like AST nodes whose get_content() aggregates auditable information
    across their composed child units.
    """

    unit_id: str
    unit_type: UnitType

    @abstractmethod
    def get_content(self) -> str:
        """Return the string representation of this unit (and any child units) for evaluation."""
        pass

    @abstractmethod
    def get_metadata(self) -> Dict[str, Any]:
        """Return unit-specific context metadata to attach to an AuditFinding."""
        pass
