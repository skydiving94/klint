import asyncio
from pathlib import Path
from typing import List, Optional, Sequence

from src.cli.file_collector import IGNORED_DIRS, IGNORED_FILES, IGNORED_SUFFIXES
from src.core.domain.units import (
    AuditableFileMetadataUnit,
    AuditableProjectDirectoryUnit,
    AuditableUnit,
)
from src.core.interfaces.extractor import BaseFileMetadataExtractor, BaseUnitExtractor
from src.infrastructure.extractors.file_metadata_extractor import (
    FallbackFileMetadataExtractor,
    PythonFileMetadataExtractor,
)


class RecursiveProjectExtractor(BaseUnitExtractor):
    """Builds a composite AuditableProjectDirectoryUnit containing metadata for
    the target directory and all of its descendant subdirectories.
    """

    def __init__(
        self,
        file_extractors: Optional[Sequence[BaseFileMetadataExtractor]] = None,
    ):
        self._file_extractors: Sequence[BaseFileMetadataExtractor] = (
            file_extractors
            if file_extractors is not None
            else (PythonFileMetadataExtractor(), FallbackFileMetadataExtractor())
        )

    async def extract(self, target: str | Path) -> List[AuditableUnit]:
        root_unit = await asyncio.to_thread(self._walk, Path(target))
        return [root_unit]

    def _walk(self, directory: Path) -> AuditableProjectDirectoryUnit:
        files: List[AuditableFileMetadataUnit] = []
        subdirs: List[AuditableProjectDirectoryUnit] = []

        for entry in sorted(directory.iterdir()):
            if entry.is_dir():
                if entry.name in IGNORED_DIRS:
                    continue
                subdirs.append(self._walk(entry))
            elif entry.is_file():
                if entry.name in IGNORED_FILES or entry.suffix.lower() in IGNORED_SUFFIXES:
                    continue
                files.append(self._extract_file_metadata(entry))

        return AuditableProjectDirectoryUnit(
            unit_id=str(directory),
            directory_path=str(directory),
            files=files,
            subdirectories=subdirs,
        )

    def _extract_file_metadata(self, path: Path) -> AuditableFileMetadataUnit:
        for extractor in self._file_extractors:
            if extractor.supports(path):
                return extractor.extract_file(path)
        return FallbackFileMetadataExtractor().extract_file(path)
