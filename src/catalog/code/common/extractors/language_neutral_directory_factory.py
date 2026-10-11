from pathlib import Path

from src.catalog.code.common.extractors.directory_factory import (
    BaseDirectoryUnitFactory,
)
from src.catalog.code.common.units.directory import AuditableDirectoryUnit
from src.catalog.code.common.units.file_metadata import AuditableFileMetadataUnit


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
            language=language,
            directory_path=str(directory_path),
            files=files,
            subdirectories=subdirectories,
        )
