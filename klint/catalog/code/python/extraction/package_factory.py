from dataclasses import replace
from pathlib import Path

from klint.catalog.code.language_neutral.extraction.directory_factory import (
    BaseDirectoryUnitFactory,
)
from klint.catalog.code.language_neutral.units.directory_unit import (
    AuditableDirectoryUnit,
)
from klint.catalog.code.language_neutral.units.file_metadata_unit import (
    AuditableFileMetadataUnit,
)
from klint.catalog.code.python.project_module_names import list_project_module_names
from klint.catalog.code.python.units.package_unit import AuditablePythonPackageUnit
from klint.core.models.unit_traits import UnitTraits


class PythonPackageUnitFactory(BaseDirectoryUnitFactory):
    """Builds Python package units and tells each one the project's module names."""

    def build_directory_unit(
        self,
        directory_path: Path,
        files: list[AuditableFileMetadataUnit],
        subdirectories: list[AuditableDirectoryUnit],
        language: str | None,
    ) -> AuditableDirectoryUnit:
        return AuditablePythonPackageUnit(
            unit_id=str(directory_path),
            traits=UnitTraits(language=language),
            directory_path=str(directory_path),
            files=files,
            subdirectories=subdirectories,
        )

    def update_units_after_full_walk(
        self, root_unit: AuditableDirectoryUnit
    ) -> AuditableDirectoryUnit:
        """Give every package in the tree the module names found anywhere in it.

        Each package can then tell the project's own imports from external ones.
        """
        if not isinstance(root_unit, AuditablePythonPackageUnit):
            return root_unit
        project_module_names = tuple(sorted(list_project_module_names(root_unit)))
        return self._attach_project_modules(root_unit, project_module_names)

    def _attach_project_modules(
        self, unit: AuditableDirectoryUnit, project_module_names: tuple[str, ...]
    ) -> AuditableDirectoryUnit:
        updated_subdirs = [
            self._attach_project_modules(sub, project_module_names)
            for sub in unit.subdirectories
        ]
        if not isinstance(unit, AuditablePythonPackageUnit):
            return replace(unit, subdirectories=updated_subdirs)
        return replace(
            unit,
            subdirectories=updated_subdirs,
            project_module_names=project_module_names,
        )
