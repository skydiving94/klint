from collections.abc import Iterator

from klint.catalog.code.language_neutral.renderers.directory import (
    format_display_path,
    list_tree_lines,
)
from klint.catalog.code.language_neutral.units.directory import AuditableDirectoryUnit
from klint.catalog.code.python.module_names import collect_module_names
from klint.catalog.code.python.units.package import AuditablePythonPackageUnit
from klint.catalog.domain_neutral.renderers.character_budget import (
    join_lines_within_budget,
)
from klint.core.interfaces.renderer import BaseUnitRenderer
from klint.core.models.render_input import RenderInput


class PythonPackageRenderer(BaseUnitRenderer):
    """Shows the judge a directory as a Python package.

    Before the tree, it shows the package's public API, the imports in its
    tree split into the project's own and external ones, and cycles between
    its subpackages. A file in its tree that cannot be parsed is named,
    since what it holds is unknown. The tree is shown as far as the
    character budget goes.
    """

    def render_subject(self, render_input: RenderInput) -> str:
        package = render_input.get_unit_as(AuditablePythonPackageUnit)
        module_names = collect_module_names(package)
        imports = _collect_imports_beneath(package)
        internal_imports = sorted(
            imp for imp in imports if _is_internal_import(imp, module_names)
        )
        external_imports = sorted(
            imp for imp in imports if not _is_internal_import(imp, module_names)
        )
        non_init_files = [
            f.file_name for f in package.files if f.file_name != "__init__.py"
        ]
        lines = [
            f"Target Directory Under Audit: {format_display_path(package)} "
            f"(package name: '{package.directory_name}')",
            f"Summary: {len(package.files)} immediate files "
            f"({len(non_init_files)} non-init modules: {non_init_files}), "
            f"{len(package.subdirectories)} immediate subdirectories",
            f"Package Public API Status: {_describe_public_api(package)}",
            "Internal Project Imports in Tree: "
            f"[{', '.join(internal_imports) if internal_imports else 'none'}]",
            "External / Third-Party / Stdlib Imports in Tree: "
            f"[{', '.join(external_imports) if external_imports else 'none'}]",
        ]
        unparseable_files = list(_list_unparseable_files_beneath(package))
        if unparseable_files:
            lines.append(
                "Files That Cannot Be Parsed in Tree: "
                f"[{', '.join(unparseable_files)}] (their imports are unknown; "
                "the import lists and cycle check here leave them out)"
            )
        lines.extend(_list_dependency_roll_up_lines(package, module_names))
        lines.extend(list_tree_lines(package))
        return join_lines_within_budget(
            lines, render_input.character_budget, "the tree"
        )


def _collect_imports_beneath(directory: AuditableDirectoryUnit) -> set[str]:
    """Return every import of the files in the tree of ``directory``."""
    imports = {imp for file_unit in directory.files for imp in file_unit.imports}
    for subdirectory in directory.subdirectories:
        imports.update(_collect_imports_beneath(subdirectory))
    return imports


def _is_internal_import(imp: str, module_names: set[str]) -> bool:
    """Return True when ``imp`` imports one of the project's own modules."""
    if imp.startswith("."):
        return True
    parts = [p for p in imp.split(".") if p]
    return bool(
        parts and (parts[0] in module_names or any(p in module_names for p in parts))
    )


def _describe_public_api(package: AuditablePythonPackageUnit) -> str:
    """Return what the package's __init__.py tells of its public API."""
    py_files = [f for f in package.files if f.language == package.language]
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
    return "minimal (__init__.py exists but declares no explicit exports or __all__)"


def _list_dependency_roll_up_lines(
    package: AuditablePythonPackageUnit, module_names: set[str]
) -> list[str]:
    """Return the lines on what each subpackage imports, and mutual cycles.

    None when the package has no subpackages.
    """
    if not package.subdirectories:
        return []
    subpackage_name_to_imports = {
        d.directory_name: sorted(_collect_imports_beneath(d))
        for d in package.subdirectories
    }
    lines = ["Subpackage Dependency Rollup:"]
    for name, imps in subpackage_name_to_imports.items():
        lines.append(f"  - {name} imports: [{', '.join(imps)}]")

    cycles: list[str] = []
    names = list(subpackage_name_to_imports)
    for i, a in enumerate(names):
        for b in names[i + 1 :]:
            a_internal = [
                imp
                for imp in subpackage_name_to_imports[a]
                if _is_internal_import(imp, module_names)
            ]
            b_internal = [
                imp
                for imp in subpackage_name_to_imports[b]
                if _is_internal_import(imp, module_names)
            ]
            does_a_import_b = any(b in imp.split(".") for imp in a_internal)
            does_b_import_a = any(a in imp.split(".") for imp in b_internal)
            if does_a_import_b and does_b_import_a:
                cycles.append(f"{a} <-> {b}")
    lines.append(
        f"  Mutual Subpackage Cycles: {', '.join(cycles) if cycles else 'none'}"
    )
    return lines


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
