from dataclasses import dataclass, field

from klint.catalog.code.language_neutral import AuditableDirectoryUnit


@dataclass(frozen=True)
class ImportGroup:
    """The imports of one kind of thing in a package, from outside its tree.

    importers are the dotted names of the modules that import it, and
    imported_names the names they import, each sorted and without repeats.
    """

    importers: tuple[str, ...] = ()
    imported_names: tuple[str, ...] = ()


@dataclass(frozen=True)
class PackageImporters:
    """What modules elsewhere in the audited tree import of a package.

    of_package are the imports of the package itself; of_subpackages, of a
    package inside it; of_modules, of a module file inside it, at any depth.
    """

    of_package: ImportGroup = field(default_factory=ImportGroup)
    of_subpackages: ImportGroup = field(default_factory=ImportGroup)
    of_modules: ImportGroup = field(default_factory=ImportGroup)


@dataclass(frozen=True)
class AuditablePythonPackageUnit(AuditableDirectoryUnit):
    """A directory read as a Python package.

    project_module_names are the module names found anywhere in its project,
    so that the project's own imports can be told from external ones.
    importers tell what the other modules of the audited tree import of it;
    None for the audited directory itself, whose callers are all outside the
    tree.
    """

    project_module_names: tuple[str, ...] = field(default_factory=tuple)
    importers: PackageImporters | None = None
