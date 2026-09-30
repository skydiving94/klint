from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, ClassVar, Dict, List, Set, Tuple

from src.core.domain.units.base import AuditableUnit
from src.core.domain.units.file_metadata import AuditableFileMetadataUnit


@dataclass(frozen=True)
class ProjectDirectoryUnitMetadata:
    directory_path: str = ""
    file_names: List[str] = field(default_factory=list)
    subdirectory_names: List[str] = field(default_factory=list)


@dataclass(frozen=True)
class AuditableProjectDirectoryUnit(AuditableUnit):
    """Composite directory unit containing its files' metadata and recursive subdirectories."""

    unit_type: ClassVar[str] = "project_directory"

    directory_path: str = ""
    files: List[AuditableFileMetadataUnit] = field(default_factory=list)
    subdirectories: List[AuditableProjectDirectoryUnit] = field(
        default_factory=list
    )
    project_module_names: Tuple[str, ...] = field(default_factory=tuple)

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

    def _get_internal_module_names(self) -> Set[str]:
        names: Set[str] = {self.directory_name, *self.project_module_names}
        for part in Path(self.directory_path).parts:
            if part not in ("", ".", "/", "\\") and not part.endswith(":"):
                names.add(part)
        for f in self.files:
            stem = Path(f.file_name).stem
            if stem and stem != "__init__":
                names.add(stem)
        for sub in self.subdirectories:
            names.update(sub._get_internal_module_names())
        return names

    def _is_internal_import(self, imp: str, known_modules: Set[str]) -> bool:
        if imp.startswith("."):
            return True
        parts = [p for p in imp.split(".") if p]
        return bool(
            parts
            and (
                parts[0] in known_modules
                or any(p in known_modules for p in parts)
            )
        )

    def get_content(self) -> str:
        known_modules = self._get_internal_module_names()
        internal_imps = sorted(
            imp
            for imp in self.get_all_imports()
            if self._is_internal_import(imp, known_modules)
        )
        lines = [
            f"Target Directory Under Audit: {self.display_path}",
            f"Summary: {len(self.files)} immediate files, {len(self.subdirectories)} immediate subdirectories",
            f"Internal Project Imports in Tree: [{', '.join(internal_imps) if internal_imps else 'none'}]",
        ]
        rollup = self._render_dependency_rollup(known_modules)
        if rollup:
            lines.append(rollup)
        lines.append(self._render_tree(indent=0))
        return "\n".join(lines)

    def _render_dependency_rollup(self, known_modules: Set[str]) -> str:
        if not self.subdirectories:
            return ""
        sub_imports = {
            d.directory_name: sorted(d.get_all_imports())
            for d in self.subdirectories
        }
        lines = ["Subpackage Dependency Rollup:"]
        for name, imps in sub_imports.items():
            lines.append(f"  - {name} imports: [{', '.join(imps)}]")

        cycles: List[str] = []
        names = list(sub_imports.keys())
        for i, a in enumerate(names):
            for b in names[i + 1:]:
                a_internal = [
                    imp
                    for imp in sub_imports[a]
                    if self._is_internal_import(imp, known_modules)
                ]
                b_internal = [
                    imp
                    for imp in sub_imports[b]
                    if self._is_internal_import(imp, known_modules)
                ]
                a_to_b = any(b in imp.split(".") for imp in a_internal)
                b_to_a = any(a in imp.split(".") for imp in b_internal)
                if a_to_b and b_to_a:
                    cycles.append(f"{a} <-> {b}")
        lines.append(
            f"  Mutual Subpackage Cycles: {', '.join(cycles) if cycles else 'none'}"
        )
        return "\n".join(lines)

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

    def get_metadata(self) -> Dict[str, Any]:
        metadata = ProjectDirectoryUnitMetadata(
            directory_path=self.directory_path,
            file_names=[f.file_name for f in self.files],
            subdirectory_names=[d.directory_name for d in self.subdirectories],
        )
        return asdict(metadata)
