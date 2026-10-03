from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Set

from src.catalog.code.common.units.file_metadata import AuditableFileMetadataUnit
from src.core.models.location import Location
from src.core.models.unit import AuditableUnit


@dataclass(frozen=True)
class ProjectDirectoryUnitMetadata:
    directory_path: str = ""
    file_names: List[str] = field(default_factory=list)
    subdirectory_names: List[str] = field(default_factory=list)


@dataclass(frozen=True)
class AuditableDirectoryUnit(AuditableUnit):
    """Composite directory unit: its files' metadata and its subdirectories.

    This base holds what is true of a directory in any language. A subclass
    declares the unit_type and decides how the directory is described to
    the judge.
    """

    directory_path: str = ""
    files: List[AuditableFileMetadataUnit] = field(default_factory=list)
    subdirectories: List[AuditableDirectoryUnit] = field(default_factory=list)

    @property
    def directory_name(self) -> str:
        path = Path(self.directory_path)
        return path.name or path.resolve().name or self.directory_path

    @property
    def display_path(self) -> str:
        if self.directory_path in (".", "./"):
            return self.directory_name
        return self.directory_path

    def get_all_imports(self) -> Set[str]:
        own = {imp for f in self.files for imp in f.imports}
        for sub in self.subdirectories:
            own.update(sub.get_all_imports())
        return own

    def _render_tree(self, indent: int = 0) -> str:
        prefix = "  " * indent
        lines = [f"{prefix}Directory: {self.display_path}"]
        if self.subdirectories:
            subdir_names = ", ".join(
                d.directory_name for d in self.subdirectories
            )
            lines.append(
                f"{prefix}  Immediate Subdirectories: [{subdir_names}]"
            )
        if self.files:
            lines.append(f"{prefix}  Files:")
            for file_unit in self.files:
                lines.append(f"{prefix}    - {file_unit.get_content()}")
        else:
            lines.append(f"{prefix}  Files: []")
        for subdir in self.subdirectories:
            lines.append(subdir._render_tree(indent=indent + 1))
        return "\n".join(lines)

    def get_location(self) -> Optional[Location]:
        return Location(source=self.directory_path or self.unit_id)

    def get_metadata(self) -> Dict[str, Any]:
        metadata = ProjectDirectoryUnitMetadata(
            directory_path=self.directory_path,
            file_names=[f.file_name for f in self.files],
            subdirectory_names=[d.directory_name for d in self.subdirectories],
        )
        return asdict(metadata)

    def children(self) -> Sequence[AuditableUnit]:
        return [*self.files, *self.subdirectories]
