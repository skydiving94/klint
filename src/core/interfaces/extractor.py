from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, List

from src.core.domain.units import AuditableFileMetadataUnit, AuditableUnit


class BaseUnitExtractor(ABC):
    @abstractmethod
    async def extract(self, target: Any) -> List[AuditableUnit]:
        pass


class BaseFileMetadataExtractor(ABC):
    """Language-specific strategy for extracting structural file metadata."""

    @abstractmethod
    def supports(self, path: Path) -> bool:
        pass

    @abstractmethod
    def extract_file(self, path: Path) -> AuditableFileMetadataUnit:
        pass
