from pathlib import Path

from klint.catalog.code.common.extraction.directory_factory import (
    BaseDirectoryUnitFactory,
)
from klint.catalog.code.common.units.directory import AuditableDirectoryUnit
from klint.catalog.code.common.units.file_metadata import AuditableFileMetadataUnit
from klint.core.models.unit_traits import UnitTraits


class LanguageNeutralDirectoryUnitFactory(BaseDirectoryUnitFactory):
    """Describes a directory by what it holds, whatever language that is in."""

    def build(
        self,
        directory_path: Path,
        files: list[AuditableFileMetadataUnit],
        subdirectories: list[AuditableDirectoryUnit],
        language: str | None,
    ) -> AuditableDirectoryUnit:
        return AuditableDirectoryUnit(
            unit_id=str(directory_path),
            traits=UnitTraits(language=language),
            directory_path=str(directory_path),
            files=files,
            subdirectories=subdirectories,
        )
