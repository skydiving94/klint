from pathlib import Path

from src.catalog.code.common.extractors.file_metadata_base import (
    BaseFileMetadataExtractor,
)
from src.catalog.code.common.units.file_metadata import AuditableFileMetadataUnit
from src.core.models.file_traits import FileTraits


class LanguageNeutralFileMetadataExtractor(BaseFileMetadataExtractor):
    """Records a file's name, path and line count, whatever its language."""

    def extract_file(self, path: Path, traits: FileTraits) -> AuditableFileMetadataUnit:
        content = path.read_text(encoding="utf-8", errors="replace")
        return AuditableFileMetadataUnit(
            unit_id=str(path),
            language=traits.language,
            file_name=path.name,
            file_path=str(path),
            line_count=len(content.splitlines()),
        )
