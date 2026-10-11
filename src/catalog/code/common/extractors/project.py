import asyncio
from pathlib import Path

from src.catalog.code.common.extractors.traits_based_extraction_delegator import (
    TraitsBasedExtractionDelegator,
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
    """Builds one composite directory unit for the whole target tree.

    The unit holds the metadata of the target's files and, recursively, of
    every subdirectory. This class only walks the tree; the delegator decides
    what reads each file and what describes each directory.
    """

    def __init__(self, delegator: TraitsBasedExtractionDelegator) -> None:
        self._delegator = delegator

    async def extract(self, target: str | Path) -> list[AuditableUnit]:
        root_unit = await asyncio.to_thread(self._extract_tree, Path(target))
        return [root_unit]

    def _extract_tree(self, target_path: Path) -> AuditableDirectoryUnit:
        return self._delegator.update_units_after_full_walk(self._walk(target_path))

    def _walk(self, directory: Path) -> AuditableDirectoryUnit:
        files: list[AuditableFileMetadataUnit] = []
        subdirs: list[AuditableDirectoryUnit] = []

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
                files.append(self._delegator.delegate_file_extraction(entry))

        return self._delegator.delegate_directory_building(directory, files, subdirs)
