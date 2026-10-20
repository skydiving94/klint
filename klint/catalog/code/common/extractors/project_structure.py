"""Extracts what a project structure audit goes through: every directory."""

from collections.abc import Iterator

from injector import inject

from klint.catalog.code.common.extractors.project import RecursiveProjectExtractor
from klint.core.interfaces.target_extractor import BaseTargetExtractor
from klint.core.models.scanned_tree import ScannedTarget
from klint.core.models.unit import AuditableUnit


class ProjectStructureExtractor(BaseTargetExtractor):
    """Extracts the directory unit of a project, and every unit nested in it.

    Raises ValueError when the target is not a directory.
    """

    @inject
    def __init__(self, project_extractor: RecursiveProjectExtractor) -> None:
        self._project_extractor = project_extractor

    async def extract_units(self, scanned_target: ScannedTarget) -> list[AuditableUnit]:
        if scanned_target.directory is None:
            raise ValueError(
                "Project structure audit target must be a directory: "
                f"{scanned_target.path}"
            )
        root_unit = await self._project_extractor.extract(scanned_target.directory)
        return list(_yield_unit_and_nested_units(root_unit))


def _yield_unit_and_nested_units(unit: AuditableUnit) -> Iterator[AuditableUnit]:
    """Yield ``unit``, then every unit nested inside it, parents before children."""
    yield unit
    for child in unit.children():
        yield from _yield_unit_and_nested_units(child)
