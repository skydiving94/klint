"""Runs an audit end to end, for any caller: a command, an API, a hook or a GUI."""

from dataclasses import dataclass
from pathlib import Path

from injector import inject

from klint.app.audit_kind_registry import AuditKindRegistry
from klint.app.audit_mode import AuditMode
from klint.app.pipeline.audit_preparer import AuditPreparer
from klint.app.pipeline.auditing import UnitAuditing
from klint.app.pipeline.roll_up import FindingRollUp
from klint.catalog.code import FILE_CONTENTS_KIND_ID, PROJECT_STRUCTURE_KIND_ID
from klint.core.interfaces.audit_progress_listener import BaseAuditProgressListener
from klint.core.interfaces.scan_progress_listener import BaseScanProgressListener
from klint.core.models.report import AuditReport

# The kind of audit each mode asks for.
_AUDIT_MODE_TO_KIND_ID = {
    AuditMode.FILE_CONTENTS: FILE_CONTENTS_KIND_ID,
    AuditMode.PROJECT_STRUCTURE: PROJECT_STRUCTURE_KIND_ID,
}


@dataclass(frozen=True)
class AuditRequest:
    """What to audit, and who to tell as the audit goes.

    target is the file or directory to audit, and audit_mode the kind of
    audit. The rules in custom_rules_source, when given, merge over the
    loaded ones. scan_progress_listener is told about each directory as it is
    scanned. audit_progress_listener is told when the audit of the units
    starts, and about each unit as its audit ends.
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
    """Runs an audit end to end, stage by stage.

    The kind of audit the request names is looked up first. The units are
    then acquired and their rules selected, the units audited, and the
    findings rolled up.
    """

    @inject
    def __init__(
        self,
        audit_kind_registry: AuditKindRegistry,
        audit_preparer: AuditPreparer,
        unit_auditing: UnitAuditing,
        finding_roll_up: FindingRollUp,
    ) -> None:
        self._audit_kind_registry = audit_kind_registry
        self._audit_preparer = audit_preparer
        self._unit_auditing = unit_auditing
        self._finding_roll_up = finding_roll_up

    async def run_audit(self, request: AuditRequest) -> AuditOutcome:
        """Audit what ``request`` names and return the outcome.

        Raises when the target or a rules file cannot be used. A unit whose
        audit fails is left out of the report and the others go on.
        """
        audit_kind = self._audit_kind_registry.find_audit_kind(
            _AUDIT_MODE_TO_KIND_ID[request.audit_mode]
        )
        portfolio = await self._audit_preparer.prepare_audit(
            request.target,
            audit_kind,
            custom_rules_source=request.custom_rules_source,
            scan_progress_listener=request.scan_progress_listener,
        )
        report = await self._unit_auditing.audit_units(
            portfolio, request.audit_progress_listener
        )
        return AuditOutcome(
            report=self._finding_roll_up.roll_up(report),
            scanned_file_count=portfolio.scanned_file_count,
            selected_unit_ids=tuple(unit.unit_id for unit in portfolio.units),
        )
