from abc import ABC, abstractmethod
from pathlib import Path
from typing import List

from src.catalog.code.common.units.directory import AuditableDirectoryUnit
from src.catalog.code.common.units.file_metadata import AuditableFileMetadataUnit


class BaseDirectoryUnitFactory(ABC):
    """Language-specific strategy for turning a walked directory into a unit."""

    @abstractmethod
    def build(
        self,
        directory: Path,
        files: List[AuditableFileMetadataUnit],
        subdirectories: List[AuditableDirectoryUnit],
    ) -> AuditableDirectoryUnit:
        """Return the unit for one directory whose contents are already built."""

    def finish(self, root: AuditableDirectoryUnit) -> AuditableDirectoryUnit:
        """Apply anything that needs the whole tree, once it has been built."""
        return root
