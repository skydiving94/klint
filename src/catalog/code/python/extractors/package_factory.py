from dataclasses import replace
from pathlib import Path
from typing import List, Tuple

from src.catalog.code.common.extractors.directory_factory import (
    BaseDirectoryUnitFactory,
)
from src.catalog.code.common.units.directory import AuditableDirectoryUnit
from src.catalog.code.common.units.file_metadata import AuditableFileMetadataUnit
from src.catalog.code.python.units.package import AuditablePythonPackageUnit


class PythonPackageUnitFactory(BaseDirectoryUnitFactory):
    """Builds Python package units and tells each one the project's module names."""

    def build(
        self,
        directory: Path,
        files: List[AuditableFileMetadataUnit],
        subdirectories: List[AuditableDirectoryUnit],
    ) -> AuditableDirectoryUnit:
        return AuditablePythonPackageUnit(
            unit_id=str(directory),
            directory_path=str(directory),
            files=files,
            subdirectories=subdirectories,
        )

    def finish(self, root: AuditableDirectoryUnit) -> AuditableDirectoryUnit:
        """Give every package in the tree the module names found anywhere in it,
        so each can tell the project's own imports from external ones."""
        if not isinstance(root, AuditablePythonPackageUnit):
            return root
        shared_modules = tuple(sorted(root.internal_module_names()))
        return self._attach_project_modules(root, shared_modules)

    def _attach_project_modules(
        self, unit: AuditableDirectoryUnit, shared_modules: Tuple[str, ...]
    ) -> AuditableDirectoryUnit:
        updated_subdirs = [
            self._attach_project_modules(sub, shared_modules)
            for sub in unit.subdirectories
        ]
        if not isinstance(unit, AuditablePythonPackageUnit):
            return replace(unit, subdirectories=updated_subdirs)
        return replace(
            unit,
            subdirectories=updated_subdirs,
            project_module_names=shared_modules,
        )
