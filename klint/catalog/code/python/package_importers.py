"""Who in an audited tree imports each Python package, and what of it.

A module is named as Python imports it. When the audited directory holds an
__init__.py, it is a package named after itself; otherwise it is a folder on
the import path, and its subdirectories are top-level packages. A folder
without an __init__.py that holds a package, outside any package, is taken
as a folder on the import path too, as a src folder or a nested project is.
"""

from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import PurePath

from klint.catalog.code.language_neutral import AuditableDirectoryUnit
from klint.catalog.code.python.package_unit import ImportGroup, PackageImporters

_INIT_FILE_NAME = "__init__.py"


@dataclass(frozen=True)
class _TreeModule:
    """A module of the tree: a package's directory, or a module file."""

    path: PurePath
    is_package: bool


@dataclass(frozen=True)
class _TreeImport:
    """One import, by a module of the tree, of a module of the tree."""

    importer_path: PurePath
    importer_name: str
    imported_name: str
    imported_module: _TreeModule


@dataclass(frozen=True)
class _FileImports:
    """A Python file's names, the names of its package, and its imports as written."""

    path: PurePath
    names: tuple[str, ...]
    package_names: tuple[str, ...]
    imports: tuple[str, ...]

    def make_absolute(self, raw_import: str) -> list[str]:
        """Return the absolute names ``raw_import`` can stand for in this file."""
        if not raw_import.startswith("."):
            return [raw_import]
        level = len(raw_import) - len(raw_import.lstrip("."))
        rest = raw_import[level:]
        absolute_names: list[str] = []
        for package_name in self.package_names:
            parts = package_name.split(".")
            if level - 1 >= len(parts):
                continue
            base = ".".join(parts[: len(parts) - (level - 1)])
            absolute_names.append(_join(base, rest))
        return absolute_names


@dataclass
class _TreeIndex:
    """The modules of a tree by the names they are imported by, and its files."""

    language: str | None
    name_to_modules: defaultdict[str, list[_TreeModule]] = field(
        default_factory=lambda: defaultdict(list)
    )
    files: list[_FileImports] = field(default_factory=list)

    def add_directory(
        self,
        directory: AuditableDirectoryUnit,
        own_names: tuple[str, ...],
        is_import_root: bool,
        is_inside_package: bool,
    ) -> None:
        """Add ``directory``, named ``own_names``, and everything beneath it."""
        child_prefixes = (("",) if is_import_root else ()) + own_names
        for name in own_names:
            self._add_module(name, PurePath(directory.directory_path), True)
        for file_unit in directory.files:
            if file_unit.language != self.language:
                continue
            path = PurePath(file_unit.file_path or file_unit.unit_id)
            if file_unit.file_name == _INIT_FILE_NAME:
                names = own_names
            else:
                names = tuple(_join(prefix, path.stem) for prefix in child_prefixes)
                for name in names:
                    self._add_module(name, path, False)
            self.files.append(
                _FileImports(path, names, own_names, tuple(file_unit.imports))
            )
        is_inside_package = is_inside_package or _has_init_file(directory)
        for subdirectory in directory.subdirectories:
            self.add_directory(
                subdirectory,
                tuple(
                    _join(prefix, subdirectory.directory_name)
                    for prefix in child_prefixes
                ),
                is_import_root=not is_inside_package
                and not _has_init_file(subdirectory)
                and any(_has_init_file(sub) for sub in subdirectory.subdirectories),
                is_inside_package=is_inside_package,
            )

    def list_imports(self) -> list[_TreeImport]:
        """Return each import, by a file of the tree, of a module of the tree."""
        imports: list[_TreeImport] = []
        for file_imports in self.files:
            importer_name = (
                file_imports.names[0] if file_imports.names else str(file_imports.path)
            )
            for raw_import in file_imports.imports:
                for candidate in file_imports.make_absolute(raw_import):
                    imported_name = self._find_longest_known_name(candidate)
                    if imported_name is None:
                        continue
                    imports.extend(
                        _TreeImport(
                            file_imports.path, importer_name, imported_name, module
                        )
                        for module in self.name_to_modules[imported_name]
                    )
        return imports

    def _add_module(self, name: str, path: PurePath, is_package: bool) -> None:
        self.name_to_modules[name].append(_TreeModule(path, is_package))

    def _find_longest_known_name(self, dotted_name: str) -> str | None:
        """Return the longest leading part of ``dotted_name`` naming a tree module."""
        parts = dotted_name.split(".")
        for end in range(len(parts), 0, -1):
            name = ".".join(parts[:end])
            if name in self.name_to_modules:
                return name
        return None


@dataclass
class _PackageImports:
    """The imports of one package from outside its tree, by what they import."""

    of_package: list[_TreeImport] = field(default_factory=list)
    of_subpackages: list[_TreeImport] = field(default_factory=list)
    of_modules: list[_TreeImport] = field(default_factory=list)

    def summarize(self) -> PackageImporters:
        return PackageImporters(
            of_package=_build_group(self.of_package),
            of_subpackages=_build_group(self.of_subpackages),
            of_modules=_build_group(self.of_modules),
        )


def map_package_path_to_importers(
    root: AuditableDirectoryUnit,
) -> dict[str, PackageImporters]:
    """Return what the rest of the tree of ``root`` imports of each directory in it.

    Each directory beneath ``root`` is keyed by its path; ``root`` itself is
    left out, since everything that imports it is outside its tree.
    """
    index = _TreeIndex(language=root.language)
    is_package = _has_init_file(root)
    index.add_directory(
        root,
        (root.directory_name,) if is_package else (),
        is_import_root=not is_package,
        is_inside_package=False,
    )
    directory_paths = [d.directory_path for d in _list_directories_beneath(root)]
    path_to_imports = {PurePath(path): _PackageImports() for path in directory_paths}
    for tree_import in index.list_imports():
        imported = tree_import.imported_module
        # The imported package's own directory, then each directory above
        # the imported module, up to the first that holds the importer too.
        for directory_path in (imported.path, *imported.path.parents):
            if directory_path in tree_import.importer_path.parents:
                break
            package_imports = path_to_imports.get(directory_path)
            if package_imports is None:
                continue
            if directory_path == imported.path:
                package_imports.of_package.append(tree_import)
            elif imported.is_package:
                package_imports.of_subpackages.append(tree_import)
            else:
                package_imports.of_modules.append(tree_import)
    return {
        path: path_to_imports[PurePath(path)].summarize() for path in directory_paths
    }


def _build_group(imports: list[_TreeImport]) -> ImportGroup:
    return ImportGroup(
        importers=tuple(sorted({i.importer_name for i in imports})),
        imported_names=tuple(sorted({i.imported_name for i in imports})),
    )


def _list_directories_beneath(
    directory: AuditableDirectoryUnit,
) -> list[AuditableDirectoryUnit]:
    """Return every directory beneath ``directory``, not counting itself."""
    directories: list[AuditableDirectoryUnit] = []
    for subdirectory in directory.subdirectories:
        directories.append(subdirectory)
        directories.extend(_list_directories_beneath(subdirectory))
    return directories


def _has_init_file(directory: AuditableDirectoryUnit) -> bool:
    return any(f.file_name == _INIT_FILE_NAME for f in directory.files)


def _join(prefix: str, name: str) -> str:
    """Return ``name`` under the dotted ``prefix``; the one set if either is empty."""
    return f"{prefix}.{name}" if prefix and name else prefix or name
