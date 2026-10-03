import asyncio
from pathlib import Path
from typing import List, Sequence

from src.catalog.code.common.extractors.directory_factory import (
    BaseDirectoryUnitFactory,
)
from src.catalog.code.common.extractors.fallback_file_metadata import (
    FallbackFileMetadataExtractor,
)
from src.catalog.code.common.extractors.file_metadata_base import (
    BaseFileMetadataExtractor,
)
from src.catalog.code.common.units.directory import AuditableDirectoryUnit
from src.catalog.code.common.units.file_metadata import AuditableFileMetadataUnit
from src.catalog.common.extractors.file_collector import (
    IGNORED_DIRS,
    IGNORED_FILES,
    IGNORED_SUFFIXES,
)
from src.core.interfaces.extractor import BaseUnitExtractor
from src.core.models.unit import AuditableUnit


class RecursiveProjectExtractor(BaseUnitExtractor):
    """Builds one composite directory unit for the target, holding the metadata
    of its files and, recursively, of every subdirectory.

    file_extractors are tried in order for each file; the first that supports
    it wins. directory_factory decides which unit describes a directory.
    """

    def __init__(
        self,
        file_extractors: Sequence[BaseFileMetadataExtractor],
        directory_factory: BaseDirectoryUnitFactory,
    ) -> None:
        self._file_extractors = tuple(file_extractors)
        self._directory_factory = directory_factory

    async def extract(self, target: str | Path) -> List[AuditableUnit]:
        root_unit = await asyncio.to_thread(self._extract_tree, Path(target))
        return [root_unit]

    def _extract_tree(self, target_path: Path) -> AuditableDirectoryUnit:
        return self._directory_factory.finish(self._walk(target_path))

    def _walk(self, directory: Path) -> AuditableDirectoryUnit:
        files: List[AuditableFileMetadataUnit] = []
        subdirs: List[AuditableDirectoryUnit] = []

        for entry in sorted(directory.iterdir()):
            if entry.is_dir():
                if entry.name in IGNORED_DIRS:
                    continue
                subdirs.append(self._walk(entry))
            elif entry.is_file():
                if (
                    entry.name in IGNORED_FILES
                    or entry.suffix.lower() in IGNORED_SUFFIXES
                ):
                    continue
                files.append(self._extract_file_metadata(entry))

        return self._directory_factory.build(directory, files, subdirs)

    def _extract_file_metadata(self, path: Path) -> AuditableFileMetadataUnit:
        for extractor in self._file_extractors:
            if extractor.supports(path):
                return extractor.extract_file(path)
        return FallbackFileMetadataExtractor().extract_file(path)
