from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import ClassVar

from klint.catalog.code.language_neutral.units.file_metadata_unit import (
    AuditableFileMetadataUnit,
)
from klint.core.models.location import Location
from klint.core.models.unit import AuditableUnit, UnitContext


@dataclass(frozen=True)
class ProjectDirectoryContext(UnitContext):
    """The names of the files and subdirectories directly in a directory."""

    file_names: list[str] = field(default_factory=list)
    subdirectory_names: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class AuditableDirectoryUnit(AuditableUnit):
    """Composite directory unit: its files' metadata and its subdirectories.

    On its own it fits a directory in any language. A subclass holds what
    one language tells about a directory.
    """

    unit_type: ClassVar[str] = "project_directory"

    directory_path: str = ""
    files: list[AuditableFileMetadataUnit] = field(default_factory=list)
    subdirectories: list[AuditableDirectoryUnit] = field(default_factory=list)

    @property
    def directory_name(self) -> str:
        path = Path(self.directory_path)
        return path.name or path.resolve().name or self.directory_path

    def get_location(self) -> Location | None:
        return Location(path=self.directory_path or self.unit_id)

    def get_context(self) -> ProjectDirectoryContext:
        return ProjectDirectoryContext(
            file_names=[f.file_name for f in self.files],
            subdirectory_names=[d.directory_name for d in self.subdirectories],
        )

    def list_children(self) -> Sequence[AuditableUnit]:
        return [*self.files, *self.subdirectories]
