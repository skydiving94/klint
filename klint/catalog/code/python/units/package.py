from dataclasses import dataclass, field

from klint.catalog.code.language_neutral.units.directory import AuditableDirectoryUnit


@dataclass(frozen=True)
class AuditablePythonPackageUnit(AuditableDirectoryUnit):
    """A directory read as a Python package.

    project_module_names are the module names found anywhere in its project,
    so that the project's own imports can be told from external ones.
    """

    project_module_names: tuple[str, ...] = field(default_factory=tuple)
