from abc import ABC, abstractmethod
from pathlib import Path

from src.catalog.code.common.units.file_metadata import AuditableFileMetadataUnit


class BaseFileMetadataExtractor(ABC):
    """Language-specific strategy for extracting structural file metadata."""

    @abstractmethod
    def supports(self, path: Path) -> bool:
        pass

    @abstractmethod
    def extract_file(self, path: Path) -> AuditableFileMetadataUnit:
        pass
