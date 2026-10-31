from abc import ABC, abstractmethod
from pathlib import Path

from klint.catalog.code.common.units.file_metadata import AuditableFileMetadataUnit
from klint.core.models.unit_traits import UnitTraits


class BaseFileMetadataExtractor(ABC):
    """Extracts the structural metadata of one file."""

    @abstractmethod
    def extract_file(self, path: Path, traits: UnitTraits) -> AuditableFileMetadataUnit:
        """Return the metadata of ``path``, given the traits identified for it."""
