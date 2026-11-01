"""The names a Python project's own modules can be imported by."""

from pathlib import Path

from klint.catalog.code.python.units.package_unit import AuditablePythonPackageUnit


def collect_module_names(package: AuditablePythonPackageUnit) -> set[str]:
    """Return the names the modules of ``package``'s project are imported by.

    They are the package's name, the module names its project was found to
    hold, the parts of its path, the names of its files' modules, and the
    same for each package beneath it.
    """
    names: set[str] = {package.directory_name, *package.project_module_names}
    for part in Path(package.directory_path).parts:
        if part not in ("", ".", "/", "\\") and not part.endswith(":"):
            names.add(part)
    for file_unit in package.files:
        stem = Path(file_unit.file_name).stem
        if stem and stem != "__init__":
            names.add(stem)
    for subdirectory in package.subdirectories:
        if isinstance(subdirectory, AuditablePythonPackageUnit):
            names.update(collect_module_names(subdirectory))
    return names
