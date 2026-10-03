import asyncio
from dataclasses import replace
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Set, Tuple

from src.cli.file_collector import IGNORED_DIRS, IGNORED_FILES, IGNORED_SUFFIXES
from src.core.models.units import (
    AuditableFileMetadataUnit,
    AuditableProjectDirectoryUnit,
    AuditableUnit,
)
from src.core.interfaces.extractor import (
    BaseFileMetadataExtractor,
    BaseUnitExtractor,
)
from src.infrastructure.extractors.file_metadata_extractor import (
    FallbackFileMetadataExtractor,
    PythonFileMetadataExtractor,
)


class RecursiveProjectExtractor(BaseUnitExtractor):
    """Builds a composite AuditableProjectDirectoryUnit containing metadata for
    the target directory and all of its descendant subdirectories, caching
    subtrees so each file is parsed at most once across a project audit.
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
        self._dir_cache: Dict[Path, Tuple[str,
                                          AuditableProjectDirectoryUnit]] = {}
        self._known_project_modules: Set[str] = set()
        self._lock = asyncio.Lock()

    async def extract(self, target: str | Path) -> List[AuditableUnit]:
        target_path = Path(target)
        async with self._lock:
            root_unit = await asyncio.to_thread(
                self._extract_with_project_context, target_path
            )
        return [root_unit]

    def _extract_with_project_context(
        self, target_path: Path
    ) -> AuditableProjectDirectoryUnit:
        unit = self._walk(target_path)
        self._known_project_modules.update(unit._get_internal_module_names())
        shared_modules = tuple(sorted(self._known_project_modules))
        if unit.project_module_names != shared_modules:
            unit = self._attach_project_modules(unit, shared_modules)
        return unit

    def _attach_project_modules(
        self,
        unit: AuditableProjectDirectoryUnit,
        shared_modules: Tuple[str, ...],
    ) -> AuditableProjectDirectoryUnit:
        updated_subdirs = [
            self._attach_project_modules(sub, shared_modules)
            for sub in unit.subdirectories
        ]
        updated = replace(
            unit,
            subdirectories=updated_subdirs,
            project_module_names=shared_modules,
        )
        resolved = Path(unit.directory_path).resolve()
        self._dir_cache[resolved] = (unit.directory_path, updated)
        return updated

    def _walk(self, directory: Path) -> AuditableProjectDirectoryUnit:
        resolved = directory.resolve()
        cached = self._dir_cache.get(resolved)
        if cached is not None and cached[0] == str(directory):
            return cached[1]

        files: List[AuditableFileMetadataUnit] = []
        subdirs: List[AuditableProjectDirectoryUnit] = []

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

        unit = AuditableProjectDirectoryUnit(
            unit_id=str(directory),
            directory_path=str(directory),
            files=files,
            subdirectories=subdirs,
            project_module_names=tuple(sorted(self._known_project_modules)),
        )
        self._dir_cache[resolved] = (str(directory), unit)
        return unit

    def _extract_file_metadata(self, path: Path) -> AuditableFileMetadataUnit:
        for extractor in self._file_extractors:
            if extractor.supports(path):
                return extractor.extract_file(path)
        return FallbackFileMetadataExtractor().extract_file(path)
