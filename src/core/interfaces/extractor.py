from abc import ABC, abstractmethod

from src.core.models.scanned_tree import ScannedFile
from src.core.models.unit import AuditableUnit


class BaseUnitExtractor(ABC):
    """Turns one scanned file into the units to audit."""

    @abstractmethod
    async def extract(self, scanned_file: ScannedFile) -> list[AuditableUnit]:
        """Return the units extracted from ``scanned_file``; there may be none."""
