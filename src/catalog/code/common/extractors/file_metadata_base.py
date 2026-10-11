from abc import ABC, abstractmethod
from pathlib import Path

from src.catalog.code.common.units.file_metadata import AuditableFileMetadataUnit
from src.core.models.file_traits import FileTraits


class BaseFileMetadataExtractor(ABC):
    """Extracts the structural metadata of one file."""

    @abstractmethod
    def extract_file(self, path: Path, traits: FileTraits) -> AuditableFileMetadataUnit:
        """Return the metadata of ``path``, given the traits identified for it."""
