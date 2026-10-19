"""Runs an audit end to end, for any caller: a command, an API, a hook or a GUI."""

from dataclasses import dataclass
from pathlib import Path

from injector import inject

from klint.app.audit_mode import AuditMode
from klint.app.audit_preparer import AuditPreparer
from klint.core.auditor import Auditor
from klint.core.interfaces.audit_progress_listener import BaseAuditProgressListener
from klint.core.interfaces.scan_progress_listener import BaseScanProgressListener
from klint.core.models.report import AuditReport


@dataclass(frozen=True)
class AuditRequest:
    """What to audit, and who to tell as the audit goes.

    target is the file or directory to audit, and audit_mode the kind of
    audit. The rules in custom_rules_source, when given, merge over the
    loaded ones. scan_progress_listener is told about each directory as it is
    scanned, and audit_progress_listener about each unit as its audit ends.
    """

    target: Path
    audit_mode: AuditMode
    custom_rules_source: Path | None = None
    scan_progress_listener: BaseScanProgressListener | None = None
    audit_progress_listener: BaseAuditProgressListener | None = None


@dataclass(frozen=True)
class AuditOutcome:
    """What one audit run gives back.

    report holds the findings and the units audited without error.
    scanned_file_count is the number of files the scan recorded.
    selected_unit_ids lists, in audit order, every unit at least one rule
    applies to; a unit listed here and missing from the report is one whose
    audit failed.
    """

    report: AuditReport
    scanned_file_count: int
    selected_unit_ids: tuple[str, ...]


class AuditPipeline:
    """Runs an audit end to end: prepares it, then audits what was prepared."""

    @inject
    def __init__(self, audit_preparer: AuditPreparer, auditor: Auditor) -> None:
        self._audit_preparer = audit_preparer
        self._auditor = auditor

    async def run_audit(self, request: AuditRequest) -> AuditOutcome:
        """Audit what ``request`` names and return the outcome.

        Raises when the target or a rules file cannot be used. A unit whose
        audit fails is left out of the report and the others go on.
        """
        portfolio = await self._audit_preparer.prepare_audit(
            request.target,
            request.audit_mode,
            custom_rules_source=request.custom_rules_source,
            scan_progress_listener=request.scan_progress_listener,
        )
        report = await self._auditor.audit(
            portfolio.units,
            portfolio.language_to_rules,
            request.audit_progress_listener,
        )
        return AuditOutcome(
            report=report,
            scanned_file_count=portfolio.scanned_file_count,
            selected_unit_ids=tuple(unit.unit_id for unit in portfolio.units),
        )
