from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import ClassVar

from klint.catalog.code.common.units.file_metadata import AuditableFileMetadataUnit
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

    On its own it describes a directory in a way that fits any language. A
    subclass describes the directory the way one language sees it.
    """

    unit_type: ClassVar[str] = "project_directory"

    directory_path: str = ""
    files: list[AuditableFileMetadataUnit] = field(default_factory=list)
    subdirectories: list[AuditableDirectoryUnit] = field(default_factory=list)

    @property
    def directory_name(self) -> str:
        path = Path(self.directory_path)
        return path.name or path.resolve().name or self.directory_path

    @property
    def display_path(self) -> str:
        if self.directory_path in (".", "./"):
            return self.directory_name
        return self.directory_path

    def get_all_imports(self) -> set[str]:
        own = {imp for f in self.files for imp in f.imports}
        for sub in self.subdirectories:
            own.update(sub.get_all_imports())
        return own

    def _render_tree(self, indent: int = 0) -> str:
        prefix = "  " * indent
        lines = [f"{prefix}Directory: {self.display_path}"]
        if self.subdirectories:
            subdir_names = ", ".join(d.directory_name for d in self.subdirectories)
            lines.append(f"{prefix}  Immediate Subdirectories: [{subdir_names}]")
        if self.files:
            lines.append(f"{prefix}  Files:")
            for file_unit in self.files:
                lines.append(f"{prefix}    - {file_unit.get_content()}")
        else:
            lines.append(f"{prefix}  Files: []")
        for subdir in self.subdirectories:
            lines.append(subdir._render_tree(indent=indent + 1))
        return "\n".join(lines)

    def get_content(self) -> str:
        lines = [
            f"Target Directory Under Audit: {self.display_path}",
            f"Summary: {len(self.files)} immediate files, "
            f"{len(self.subdirectories)} immediate subdirectories",
            self._render_tree(indent=0),
        ]
        return "\n".join(lines)

    def get_location(self) -> Location | None:
        return Location(source=self.directory_path or self.unit_id)

    def get_context(self) -> ProjectDirectoryContext:
        return ProjectDirectoryContext(
            file_names=[f.file_name for f in self.files],
            subdirectory_names=[d.directory_name for d in self.subdirectories],
        )

    def children(self) -> Sequence[AuditableUnit]:
        return [*self.files, *self.subdirectories]
