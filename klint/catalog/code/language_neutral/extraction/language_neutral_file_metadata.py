from klint.catalog.code.language_neutral.extraction.file_metadata_base import (
    BaseFileMetadataExtractor,
    list_binary_file,
)
from klint.catalog.code.language_neutral.units.file_metadata import (
    AuditableFileMetadataUnit,
)
from klint.catalog.domain_neutral.extraction.dispatched_file import DispatchedFile


class LanguageNeutralFileMetadataExtractor(BaseFileMetadataExtractor):
    """Records a file's name, path and line count, whatever its language."""

    def extract_file(
        self, dispatched_file: DispatchedFile
    ) -> AuditableFileMetadataUnit:
        if dispatched_file.is_binary:
            return list_binary_file(dispatched_file)
        path = dispatched_file.path
        content = path.read_text(encoding="utf-8", errors="replace")
        return AuditableFileMetadataUnit(
            unit_id=str(path),
            traits=dispatched_file.traits,
            file_name=path.name,
            file_path=str(path),
            line_count=len(content.splitlines()),
        )
