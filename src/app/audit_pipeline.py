"""Prepares an audit: works out what will be audited before any rule is applied."""

import asyncio
from collections.abc import Iterator, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import assert_never

from src.app.audit_mode import AuditMode
from src.catalog.code.common.extractors.project import RecursiveProjectExtractor
from src.catalog.common.scanners.target_scanner import TargetScanner
from src.core.interfaces.extractor import BaseUnitExtractor
from src.core.interfaces.scan_progress_listener import BaseScanProgressListener
from src.core.klint_warning import warn_about_unreadable_file
from src.core.models.scanned_tree import ScannedDirectory, ScannedFile
from src.core.models.unit import AuditableUnit


@dataclass(frozen=True)
class PendingAuditPortfolio:
    """Everything one audit run will go through, prepared and not yet audited.

    targets are the paths the run reports on. units are what the rules will
    be applied to: the units extracted for each target, with the units nested
    inside them.
    """

    targets: list[Path]
    units: list[AuditableUnit]


class AuditPipeline:
    """Prepares an audit of a target, in fixed steps.

    The target is scanned once. The units are then extracted from what the
    scan found, each file by the extractor that matches its traits. No rule
    is applied here and no judge is asked.
    """

    def __init__(
        self,
        target_scanner: TargetScanner,
        language_to_unit_extractor: Mapping[str, BaseUnitExtractor],
        language_neutral_unit_extractor: BaseUnitExtractor,
        project_extractor: RecursiveProjectExtractor,
    ) -> None:
        self._target_scanner = target_scanner
        self._language_to_unit_extractor = {
            language.lower(): extractor
            for language, extractor in language_to_unit_extractor.items()
        }
        self._language_neutral_unit_extractor = language_neutral_unit_extractor
        self._project_extractor = project_extractor

    async def prepare_audit(
        self,
        target: Path,
        audit_mode: AuditMode,
        scan_progress_listener: BaseScanProgressListener | None = None,
    ) -> PendingAuditPortfolio:
        """Scan ``target`` and extract what will be audited; raise if it cannot be.

        The listener, when given, is told about each directory as it is scanned.
        """
        match audit_mode:
            case AuditMode.FILE_CONTENTS:
                return await self._prepare_file_contents_audit(
                    target, scan_progress_listener
                )
            case AuditMode.PROJECT_STRUCTURE:
                return await self._prepare_project_structure_audit(
                    target, scan_progress_listener
                )
            case _:
                assert_never(audit_mode)

    async def _prepare_file_contents_audit(
        self, target: Path, scan_progress_listener: BaseScanProgressListener | None
    ) -> PendingAuditPortfolio:
        scanned_files = await asyncio.to_thread(
            self._scan_files, target, scan_progress_listener
        )
        targets: list[Path] = []
        units: list[AuditableUnit] = []
        for scanned_file in scanned_files:
            file_units = await self._extract_file_units(scanned_file)
            if file_units:
                targets.append(scanned_file.path)
                units.extend(file_units)
        return PendingAuditPortfolio(targets=targets, units=units)

    def _scan_files(
        self, target: Path, scan_progress_listener: BaseScanProgressListener | None
    ) -> list[ScannedFile]:
        if not target.exists():
            raise FileNotFoundError(f"Audit target does not exist: {target}")
        if target.is_file():
            return [self._target_scanner.scan_file(target)]
        if not target.is_dir():
            # Neither a file nor a directory, such as a named pipe: it holds
            # no file to audit.
            return []
        scanned_target = self._target_scanner.scan_directory(
            target, scan_progress_listener
        )
        return list(scanned_target.yield_files())

    async def _extract_file_units(
        self, scanned_file: ScannedFile
    ) -> list[AuditableUnit]:
        """Return the units of one file, from the extractor that matches its traits.

        A file that cannot be read gives no unit, and a warning.
        """
        extractor = self._language_neutral_unit_extractor
        language = scanned_file.traits.language
        if language is not None:
            extractor = self._language_to_unit_extractor.get(
                language.lower(), extractor
            )
        try:
            return await extractor.extract(scanned_file)
        except OSError as error:
            warn_about_unreadable_file(scanned_file.path, error)
            return []

    async def _prepare_project_structure_audit(
        self, target: Path, scan_progress_listener: BaseScanProgressListener | None
    ) -> PendingAuditPortfolio:
        scanned_target = await asyncio.to_thread(
            self._scan_project, target, scan_progress_listener
        )
        root_unit = await self._project_extractor.extract(scanned_target)
        return PendingAuditPortfolio(
            targets=[
                scanned_directory.path
                for scanned_directory in scanned_target.yield_directories()
            ],
            units=list(_yield_unit_and_nested_units(root_unit)),
        )

    def _scan_project(
        self, target: Path, scan_progress_listener: BaseScanProgressListener | None
    ) -> ScannedDirectory:
        if not target.exists():
            raise FileNotFoundError(
                f"Project structure audit target does not exist: {target}"
            )
        if not target.is_dir():
            raise ValueError(
                f"Project structure audit target must be a directory: {target}"
            )
        return self._target_scanner.scan_directory(target, scan_progress_listener)


def _yield_unit_and_nested_units(unit: AuditableUnit) -> Iterator[AuditableUnit]:
    """Yield ``unit``, then every unit nested inside it, parents before children."""
    yield unit
    for child in unit.children():
        yield from _yield_unit_and_nested_units(child)
