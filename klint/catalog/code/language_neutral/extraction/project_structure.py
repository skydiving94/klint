"""Extracts what a project structure audit goes through: every directory."""

from collections.abc import Iterator

from injector import inject

from klint.catalog.code.language_neutral.extraction.directory_tree_extractor import (
    DirectoryTreeExtractor,
)
from klint.core.interfaces.extractor import BaseUnitExtractor
from klint.core.models.scanned_tree import ScannedTarget
from klint.core.models.unit import AuditableUnit


class ProjectStructureExtractor(BaseUnitExtractor[ScannedTarget]):
    """Extracts the directory unit of a project, and every unit nested in it.

    Raises ValueError when the target is not a directory.
    """

    @inject
    def __init__(self, directory_tree_extractor: DirectoryTreeExtractor) -> None:
        self._project_extractor = directory_tree_extractor

    async def extract(self, audit_input: ScannedTarget) -> list[AuditableUnit]:
        if audit_input.directory is None:
            raise ValueError(
                "Project structure audit target must be a directory: "
                f"{audit_input.path}"
            )
        root_unit = await self._project_extractor.extract(audit_input.directory)
        return list(_yield_unit_and_nested_units(root_unit))


def _yield_unit_and_nested_units(unit: AuditableUnit) -> Iterator[AuditableUnit]:
    """Yield ``unit``, then every unit nested inside it, parents before children."""
    yield unit
    for child in unit.list_children():
        yield from _yield_unit_and_nested_units(child)
