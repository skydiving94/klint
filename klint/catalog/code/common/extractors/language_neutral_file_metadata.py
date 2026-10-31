from pathlib import Path

from klint.catalog.code.common.extractors.file_metadata_base import (
    BaseFileMetadataExtractor,
)
from klint.catalog.code.common.units.file_metadata import AuditableFileMetadataUnit
from klint.core.models.unit_traits import UnitTraits


class LanguageNeutralFileMetadataExtractor(BaseFileMetadataExtractor):
    """Records a file's name, path and line count, whatever its language."""

    def extract_file(self, path: Path, traits: UnitTraits) -> AuditableFileMetadataUnit:
        content = path.read_text(encoding="utf-8", errors="replace")
        return AuditableFileMetadataUnit(
            unit_id=str(path),
            traits=traits,
            file_name=path.name,
            file_path=str(path),
            line_count=len(content.splitlines()),
        )
