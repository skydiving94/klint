"""Reads an audit input from disk as a tree of the directories and files it holds."""

import asyncio
from pathlib import Path

from klint.catalog.common.scanners.target_scanner import TargetScanner
from klint.core.interfaces.file_traits_identifier import BaseFileTraitsIdentifier
from klint.core.interfaces.scan_progress_listener import BaseScanProgressListener
from klint.core.interfaces.source import BaseAuditSource, BaseAuditSourceFactory
from klint.core.models.audit_input import (
    AuditInput,
    DiskPathInput,
    InMemoryBytesInput,
)
from klint.core.models.ignored_names import IgnoredNames
from klint.core.models.scanned_tree import ScannedTarget


class DirectoryTreeSource(BaseAuditSource[ScannedTarget]):
    """Scans one file or directory on disk, once, with a target scanner."""

    def __init__(
        self,
        target_scanner: TargetScanner,
        target: Path,
        scan_progress_listener: BaseScanProgressListener | None = None,
    ) -> None:
        self._target_scanner = target_scanner
        self._target = target
        self._scan_progress_listener = scan_progress_listener
        self._scanned_file_count = 0

    async def read_input(self) -> ScannedTarget:
        """Return what the target holds. Raises when it does not exist."""
        scanned_target = await asyncio.to_thread(
            self._target_scanner.scan_target,
            self._target,
            self._scan_progress_listener,
        )
        self._scanned_file_count = len(scanned_target.files)
        return scanned_target

    def count_scanned_files(self) -> int:
        return self._scanned_file_count


class DirectoryTreeSourceFactory(BaseAuditSourceFactory[ScannedTarget]):
    """Makes a directory tree source for each path on disk.

    The scan identifies each file's traits with ``file_traits_identifier``
    and leaves out ``ignored_names``.
    """

    def __init__(
        self,
        file_traits_identifier: BaseFileTraitsIdentifier,
        ignored_names: IgnoredNames,
    ) -> None:
        self._target_scanner = TargetScanner(file_traits_identifier, ignored_names)

    def create_source(
        self,
        audit_input: AuditInput,
        scan_progress_listener: BaseScanProgressListener | None = None,
    ) -> DirectoryTreeSource:
        match audit_input:
            case DiskPathInput(path=path):
                return DirectoryTreeSource(
                    self._target_scanner, path, scan_progress_listener
                )
            case InMemoryBytesInput():
                raise ValueError(
                    "A directory tree is read from a path on disk, "
                    "not from content in memory"
                )
