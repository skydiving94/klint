"""The acquisition stage: what a run goes through, read from its target."""

import asyncio
from dataclasses import dataclass
from pathlib import Path

from injector import inject

from klint.catalog.common.scanners.target_scanner import TargetScanner
from klint.core.interfaces.file_traits_identifier import BaseFileTraitsIdentifier
from klint.core.interfaces.scan_progress_listener import BaseScanProgressListener
from klint.core.models.audit_kind import AuditKind
from klint.core.models.unit import AuditableUnit


@dataclass(frozen=True)
class AcquiredUnits:
    """The units read from one audit target.

    units are every unit the kind of audit extracts from the target, nested
    ones included, each before the units nested inside it.
    scanned_file_count is the number of files the scan recorded.
    """

    units: list[AuditableUnit]
    scanned_file_count: int


class UnitAcquisition:
    """Scans an audit target once and extracts its units by the kind of audit.

    The scan leaves out the names the kind ignores.
    """

    @inject
    def __init__(self, file_traits_identifier: BaseFileTraitsIdentifier) -> None:
        self._file_traits_identifier = file_traits_identifier

    async def acquire_units(
        self,
        target: Path,
        audit_kind: AuditKind,
        scan_progress_listener: BaseScanProgressListener | None = None,
    ) -> AcquiredUnits:
        """Return the units of ``target`` for ``audit_kind``.

        Raises when the target cannot be used. The listener, when given, is
        told about each directory as it is scanned.
        """
        target_scanner = TargetScanner(
            self._file_traits_identifier, audit_kind.ignored_names
        )
        scanned_target = await asyncio.to_thread(
            target_scanner.scan_target, target, scan_progress_listener
        )
        return AcquiredUnits(
            units=await audit_kind.extractor.extract_units(scanned_target),
            scanned_file_count=len(scanned_target.files),
        )
