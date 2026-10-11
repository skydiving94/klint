"""Prepares an audit: works out what will be audited before any rule is applied."""

import asyncio
from dataclasses import dataclass
from pathlib import Path
from typing import assert_never

from src.app.audit_mode import AuditMode
from src.catalog.common.extractors.binary_check import is_likely_binary
from src.catalog.common.scanners.target_scanner import TargetScanner


@dataclass(frozen=True)
class PendingAuditPortfolio:
    """Everything one audit run will go through, prepared and not yet audited."""

    targets: list[Path]


class AuditPipeline:
    """Prepares an audit of a target, in fixed steps.

    The target is scanned once, and what the scan found is handed over for
    the kind of audit that was asked for. No rule is applied here and no
    judge is asked.
    """

    def __init__(self, target_scanner: TargetScanner) -> None:
        self._target_scanner = target_scanner

    async def prepare_audit(
        self, target: Path, audit_mode: AuditMode
    ) -> PendingAuditPortfolio:
        """Scan ``target`` and return what will be audited; raise if it cannot be."""
        targets = await asyncio.to_thread(self._list_targets, target, audit_mode)
        return PendingAuditPortfolio(targets=targets)

    def _list_targets(self, target: Path, audit_mode: AuditMode) -> list[Path]:
        match audit_mode:
            case AuditMode.FILE_CONTENTS:
                return self._list_files_to_audit(target)
            case AuditMode.PROJECT_STRUCTURE:
                return self._list_directories_to_audit(target)
            case _:
                assert_never(audit_mode)

    def _list_files_to_audit(self, target: Path) -> list[Path]:
        if not target.exists():
            raise FileNotFoundError(f"Audit target does not exist: {target}")
        if target.is_file():
            return [self._target_scanner.scan_file(target).path]
        scanned_target = self._target_scanner.scan_directory(target)
        return [
            scanned_file.path
            for scanned_file in scanned_target.yield_files()
            if not is_likely_binary(scanned_file.path)
        ]

    def _list_directories_to_audit(self, target: Path) -> list[Path]:
        if not target.exists():
            raise FileNotFoundError(
                f"Project structure audit target does not exist: {target}"
            )
        if not target.is_dir():
            raise ValueError(
                f"Project structure audit target must be a directory: {target}"
            )
        scanned_target = self._target_scanner.scan_directory(target)
        return [
            scanned_directory.path
            for scanned_directory in scanned_target.yield_directories()
        ]
