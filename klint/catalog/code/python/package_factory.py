from dataclasses import replace
from pathlib import Path

from klint.catalog.code.language_neutral import (
    AuditableDirectoryUnit,
    AuditableFileMetadataUnit,
)
from klint.catalog.code.language_neutral.extraction import BaseDirectoryUnitFactory
from klint.catalog.code.python.package_importers import map_package_path_to_importers
from klint.catalog.code.python.package_unit import (
    AuditablePythonPackageUnit,
    PackageImporters,
)
from klint.catalog.code.python.project_module_names import list_project_module_names
from klint.core.models.units import UnitTraits


class PythonPackageUnitFactory(BaseDirectoryUnitFactory):
    """Builds Python package units and tells each one what its whole tree shows."""

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
        """Tell every package in the tree what the whole tree shows of it.

        Each package is given the module names found anywhere in the tree, so
        that it can tell the project's own imports from external ones, and
        what the other modules of the tree import of it.
        """
        if not isinstance(root_unit, AuditablePythonPackageUnit):
            return root_unit
        return self._attach_tree_facts(
            root_unit,
            tuple(sorted(list_project_module_names(root_unit))),
            map_package_path_to_importers(root_unit),
        )

    def _attach_tree_facts(
        self,
        unit: AuditableDirectoryUnit,
        project_module_names: tuple[str, ...],
        package_path_to_importers: dict[str, PackageImporters],
    ) -> AuditableDirectoryUnit:
        updated_subdirs = [
            self._attach_tree_facts(
                sub, project_module_names, package_path_to_importers
            )
            for sub in unit.subdirectories
        ]
        if not isinstance(unit, AuditablePythonPackageUnit):
            return replace(unit, subdirectories=updated_subdirs)
        return replace(
            unit,
            subdirectories=updated_subdirs,
            project_module_names=project_module_names,
            importers=package_path_to_importers.get(unit.directory_path),
        )
