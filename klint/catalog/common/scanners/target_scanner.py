"""Scans an audit target once and records the directories and files it holds."""

from dataclasses import dataclass
from pathlib import Path

from injector import inject

from klint.core.interfaces.file_traits_identifier import BaseFileTraitsIdentifier
from klint.core.interfaces.scan_progress_listener import BaseScanProgressListener
from klint.core.klint_warning import warn_about_unreadable_directory
from klint.core.models.scanned_tree import ScannedDirectory, ScannedFile


@dataclass(frozen=True)
class IgnoredNames:
    """The names a scan leaves out.

    directory_names and file_names are compared with the name of an entry.
    file_suffixes are compared with the suffix of a file in lower case, with
    its leading dot, such as ".png".
    """

    directory_names: frozenset[str] = frozenset()
    file_names: frozenset[str] = frozenset()
    file_suffixes: frozenset[str] = frozenset()


class TargetScanner:
    """Finds the directories and files of an audit target.

    Each directory is listed once and no file is opened: the traits of a file
    are identified from the outside. An entry with an ignored name is left
    out wherever it sits beneath the target. The folders above the target are
    not looked at. A link to a directory is not followed. A directory that
    cannot be read is left out, with a warning.
    """

    @inject
    def __init__(
        self,
        file_traits_identifier: BaseFileTraitsIdentifier,
        ignored_names: IgnoredNames,
    ) -> None:
        self._file_traits_identifier = file_traits_identifier
        self._ignored_names = ignored_names

    def scan_file(self, file_path: Path) -> ScannedFile:
        """Return the file at ``file_path`` with its traits, as a target of its own."""
        return ScannedFile(
            path=file_path, traits=self._file_traits_identifier.identify(file_path)
        )

    def scan_directory(
        self,
        directory: Path,
        scan_progress_listener: BaseScanProgressListener | None = None,
    ) -> ScannedDirectory:
        """Return ``directory`` and everything kept beneath it, as a tree.

        The listener, when given, is told about each directory right after it
        is listed: the target first, then the others in path order. When the
        target itself cannot be read, it is returned with nothing in it.
        """
        scanned_target = self._scan_directory(directory, None, scan_progress_listener)
        if scanned_target is None:
            return ScannedDirectory(path=directory)
        return scanned_target

    def _scan_directory(
        self,
        directory: Path,
        parent: ScannedDirectory | None,
        scan_progress_listener: BaseScanProgressListener | None,
    ) -> ScannedDirectory | None:
        """Return ``directory`` as a tree; None when it cannot be read."""
        entries = self._list_entries(directory)
        if entries is None:
            return None
        scanned_directory = ScannedDirectory(path=directory, parent=parent)
        if scan_progress_listener is not None:
            scan_progress_listener.report_directory_scanned(directory)
        for entry in entries:
            if entry.is_dir():
                if self._is_ignored_directory(entry):
                    continue
                scanned_subdirectory = self._scan_directory(
                    entry, scanned_directory, scan_progress_listener
                )
                if scanned_subdirectory is not None:
                    scanned_directory.subdirectories.append(scanned_subdirectory)
            elif entry.is_file() and not self._is_ignored_file(entry):
                scanned_directory.files.append(
                    ScannedFile(
                        path=entry,
                        traits=self._file_traits_identifier.identify(entry),
                        parent=scanned_directory,
                    )
                )
        return scanned_directory

    def _list_entries(self, directory: Path) -> list[Path] | None:
        """Return the entries of ``directory`` in path order.

        None, with a warning, when the directory cannot be read.
        """
        try:
            return sorted(directory.iterdir())
        except OSError as error:
            warn_about_unreadable_directory(directory, error)
            return None

    def _is_ignored_directory(self, directory: Path) -> bool:
        return (
            directory.is_symlink()
            or directory.name in self._ignored_names.directory_names
        )

    def _is_ignored_file(self, file_path: Path) -> bool:
        return (
            file_path.name in self._ignored_names.file_names
            or file_path.suffix.lower() in self._ignored_names.file_suffixes
        )
