from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path

from klint.catalog.code.common.units.directory import AuditableDirectoryUnit


@dataclass(frozen=True)
class AuditablePythonPackageUnit(AuditableDirectoryUnit):
    """A directory described as a Python package.

    The description covers its public API, the imports in its tree split into
    internal and external, and cycles between its subpackages. A file in its
    tree that cannot be parsed is named, since what it holds is unknown.
    """

    project_module_names: tuple[str, ...] = field(default_factory=tuple)

    def internal_module_names(self) -> set[str]:
        names: set[str] = {self.directory_name, *self.project_module_names}
        for part in Path(self.directory_path).parts:
            if part not in ("", ".", "/", "\\") and not part.endswith(":"):
                names.add(part)
        for f in self.files:
            stem = Path(f.file_name).stem
            if stem and stem != "__init__":
                names.add(stem)
        for sub in self.subdirectories:
            if isinstance(sub, AuditablePythonPackageUnit):
                names.update(sub.internal_module_names())
        return names

    def _is_internal_import(self, imp: str, known_modules: set[str]) -> bool:
        if imp.startswith("."):
            return True
        parts = [p for p in imp.split(".") if p]
        return bool(
            parts
            and (parts[0] in known_modules or any(p in known_modules for p in parts))
        )

    def _describe_public_api(self) -> str:
        py_files = [f for f in self.files if f.language == self.language]
        if not py_files:
            return "not applicable (no immediate .py files in this directory)"
        init_file = next((f for f in py_files if f.file_name == "__init__.py"), None)
        if init_file is None:
            return (
                "MISSING (__init__.py is absent; internal modules are exposed "
                "without a package public API)"
            )
        if init_file.is_unparseable:
            return "unknown (__init__.py cannot be parsed)"
        if init_file.exports:
            return f"present (__init__.py exports: [{', '.join(init_file.exports)}])"
        return (
            "minimal (__init__.py exists but declares no explicit exports or __all__)"
        )

    def get_content(self) -> str:
        known_modules = self.internal_module_names()
        all_imps = self.get_all_imports()
        internal_imps = sorted(
            imp for imp in all_imps if self._is_internal_import(imp, known_modules)
        )
        external_imps = sorted(
            imp for imp in all_imps if not self._is_internal_import(imp, known_modules)
        )
        non_init_files = [
            f.file_name for f in self.files if f.file_name != "__init__.py"
        ]
        lines = [
            f"Target Directory Under Audit: {self.display_path} "
            f"(package name: '{self.directory_name}')",
            f"Summary: {len(self.files)} immediate files "
            f"({len(non_init_files)} non-init modules: {non_init_files}), "
            f"{len(self.subdirectories)} immediate subdirectories",
            f"Package Public API Status: {self._describe_public_api()}",
            "Internal Project Imports in Tree: "
            f"[{', '.join(internal_imps) if internal_imps else 'none'}]",
            "External / Third-Party / Stdlib Imports in Tree: "
            f"[{', '.join(external_imps) if external_imps else 'none'}]",
        ]
        unparseable_files = list(_list_unparseable_files_beneath(self))
        if unparseable_files:
            lines.append(
                "Files That Cannot Be Parsed in Tree: "
                f"[{', '.join(unparseable_files)}] (their imports are unknown; "
                "the import lists and cycle check here leave them out)"
            )
        rollup = self._render_dependency_rollup(known_modules)
        if rollup:
            lines.append(rollup)
        lines.append(self._render_tree(indent=0))
        return "\n".join(lines)

    def _render_dependency_rollup(self, known_modules: set[str]) -> str:
        if not self.subdirectories:
            return ""
        sub_imports = {
            d.directory_name: sorted(d.get_all_imports()) for d in self.subdirectories
        }
        lines = ["Subpackage Dependency Rollup:"]
        for name, imps in sub_imports.items():
            lines.append(f"  - {name} imports: [{', '.join(imps)}]")

        cycles: list[str] = []
        names = list(sub_imports.keys())
        for i, a in enumerate(names):
            for b in names[i + 1 :]:
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


def _list_unparseable_files_beneath(
    directory: AuditableDirectoryUnit,
) -> Iterator[str]:
    """Yield each file in the tree of ``directory`` that cannot be parsed.

    Each is given by its path from ``directory``, in the order the tree is
    described.
    """
    for file_unit in directory.files:
        if file_unit.is_unparseable:
            yield file_unit.file_name
    for subdirectory in directory.subdirectories:
        for path in _list_unparseable_files_beneath(subdirectory):
            yield f"{subdirectory.directory_name}/{path}"
