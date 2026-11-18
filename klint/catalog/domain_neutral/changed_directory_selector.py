"""Limits an audit of directories to those that hold a changed file."""

from collections.abc import Sequence
from pathlib import Path

from klint.core.interfaces import BaseUnitSelector
from klint.core.models.scanning import IgnoredNames
from klint.core.models.units import AuditableUnit


class ChangedDirectorySelector(BaseUnitSelector):
    """Keeps the directory units that hold a changed path, and their parents.

    A directory unit is one whose location is a directory on disk; a unit
    located at a file stands for a file the audit read. changed_paths are
    the paths a change touches, before and after it, each as the audit names
    files. A path that is a file on disk counts when the audit read it. A
    path gone from disk, such as a deleted file, counts when the scan would
    have read it: the nearest directory still on disk holds it. ignored_names
    are the names the scan leaves out. offered_directory_count is the number
    of directory units the last selection was given, and selected_units what
    it kept, parents first.
    """

    def __init__(
        self, changed_paths: Sequence[Path], ignored_names: IgnoredNames
    ) -> None:
        self._changed_paths = tuple(changed_paths)
        self._ignored_names = ignored_names
        self.offered_directory_count = 0
        self.selected_units: list[AuditableUnit] = []

    def select_units(self, units: Sequence[AuditableUnit]) -> list[AuditableUnit]:
        path_to_directory: dict[Path, AuditableUnit] = {}
        read_file_paths: set[Path] = set()
        for unit in units:
            location = unit.get_location()
            if location is None:
                continue
            path = Path(location.path).resolve()
            if path.is_dir():
                path_to_directory[path] = unit
            else:
                read_file_paths.add(path)
        kept_directories: set[Path] = set()
        for changed_path in self._changed_paths:
            holder = self._find_holding_directory(
                changed_path.resolve(), path_to_directory, read_file_paths
            )
            if holder is not None:
                kept_directories.update(
                    path
                    for path in (holder, *holder.parents)
                    if path in path_to_directory
                )
        self.offered_directory_count = len(path_to_directory)
        self.selected_units = [
            unit for path, unit in path_to_directory.items() if path in kept_directories
        ]
        return list(self.selected_units)

    def _find_holding_directory(
        self,
        path: Path,
        path_to_directory: dict[Path, AuditableUnit],
        read_file_paths: set[Path],
    ) -> Path | None:
        """Return the audited directory that holds ``path``; None when none does."""
        if path.exists():
            return path.parent if path in read_file_paths else None
        if self._is_ignored_file(path):
            return None
        for directory in path.parents:
            if directory in path_to_directory:
                return directory
            # A directory still on disk that the audit did not read was left
            # out, and so was everything in it.
            if directory.exists() or self._is_ignored_directory(directory):
                return None
        return None

    def _is_ignored_file(self, path: Path) -> bool:
        return (
            path.name in self._ignored_names.file_names
            or path.suffix.lower() in self._ignored_names.file_suffixes
        )

    def _is_ignored_directory(self, path: Path) -> bool:
        return path.name in self._ignored_names.directory_names
