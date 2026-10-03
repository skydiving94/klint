from pathlib import Path

from src.catalog.code.common.extractors.file_metadata_base import (
    BaseFileMetadataExtractor,
)
from src.catalog.code.common.units.file_metadata import AuditableFileMetadataUnit


class FallbackFileMetadataExtractor(BaseFileMetadataExtractor):
    """Fallback extractor that records basic file identity and line count."""

    def supports(self, path: Path) -> bool:
        return True

    def extract_file(self, path: Path) -> AuditableFileMetadataUnit:
        content = path.read_text(encoding="utf-8", errors="replace")
        return AuditableFileMetadataUnit(
            unit_id=str(path),
            file_name=path.name,
            file_path=str(path),
            line_count=len(content.splitlines()),
        )
