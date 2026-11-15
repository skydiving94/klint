"""Brings the acknowledgement log up to date with an audit of the staged change."""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from klint.app.acknowledgements.finding_identity import (
    FindingIdentity,
    describe_unit_name,
    identify_finding,
    relate_path_to_repository,
)
from klint.app.acknowledgements.matching import AcknowledgedFinding
from klint.core.models.reports import (
    AcknowledgementEntry,
    AcknowledgementStatus,
    AuditFinding,
    FlaggedFinding,
    FlaggedUnit,
)
from klint.core.models.units import AuditableUnit
from klint.infra.acknowledgement_log import FileAcknowledgementLog


@dataclass(frozen=True)
class UnitKey:
    """A unit as the log names it: its file from the repository's root, and its name."""

    file: str
    name: str


@dataclass(frozen=True)
class StagedUnits:
    """What the staged change holds, for reconciling the log with its audit.

    files are the changed files, deleted ones included, from the
    repository's root. selected_units are the units the audit judged, and
    offered_units every unit the changed files hold, judged or not.
    """

    files: frozenset[str]
    selected_units: Sequence[AuditableUnit]
    offered_units: Sequence[AuditableUnit]


@dataclass(frozen=True)
class LogReconciliation:
    """What reconciling did to the log, and what it leaves open.

    added_entries were created open for new findings, and removed_entries
    were open entries whose finding is gone. acknowledged_findings are the
    findings an acknowledged entry covers. open_entries are the entries
    still open for the staged change's files, which block the commit.
    """

    added_entries: tuple[AcknowledgementEntry, ...]
    removed_entries: tuple[AcknowledgementEntry, ...]
    acknowledged_findings: tuple[AcknowledgedFinding, ...]
    open_entries: tuple[AcknowledgementEntry, ...]

    def did_change_log(self) -> bool:
        return bool(self.added_entries or self.removed_entries)


def format_timestamp_now() -> str:
    """Return the present time as the log writes a timestamp."""
    return datetime.now(UTC).isoformat(timespec="seconds")


def reconcile_log(
    log: FileAcknowledgementLog,
    open_findings: Sequence[AuditFinding],
    acknowledged_findings: Sequence[AcknowledgedFinding],
    staged: StagedUnits,
    repository_root: Path,
    working_directory: Path,
    judge_model_version: str | None,
    flagged_at: str,
) -> LogReconciliation:
    """Update ``log`` with what the audit of ``staged`` found.

    ``open_findings`` are the problems no acknowledged entry covers, and
    ``acknowledged_findings`` those one does. Only the entries of the staged
    change are touched: those on a unit the audit judged, or on a unit its
    file no longer holds. Among them, an open entry whose finding is gone
    is removed, and a finding with no entry gets an open one, flagged at
    ``flagged_at`` by ``judge_model_version``. Acknowledged entries stay as
    they are. Raises ValueError naming the file when an entry cannot be
    read.
    """
    entries = log.list_entries()
    selected_keys = _build_unit_keys(
        staged.selected_units, repository_root, working_directory
    )
    offered_keys = _build_unit_keys(
        staged.offered_units, repository_root, working_directory
    )

    def is_reconciled(entry: AcknowledgementEntry) -> bool:
        key = UnitKey(entry.unit.file, entry.unit.name)
        return key.file in staged.files and (
            key in selected_keys or key not in offered_keys
        )

    identity_to_finding = {
        identity: finding
        for finding in open_findings
        if (identity := identify_finding(finding, repository_root, working_directory))
        is not None
    }
    standing_entry_ids = {identity.build_entry_id() for identity in identity_to_finding}
    existing_entry_ids = {entry.entry_id for entry in entries}
    removed = tuple(
        entry
        for entry in entries
        if entry.is_open()
        and is_reconciled(entry)
        and entry.entry_id not in standing_entry_ids
    )
    for entry in removed:
        log.remove_entry(entry.entry_id)
    added = tuple(
        _build_open_entry(
            identity, finding, selected_keys, judge_model_version, flagged_at
        )
        for identity, finding in identity_to_finding.items()
        if identity.build_entry_id() not in existing_entry_ids
    )
    for entry in added:
        log.write_entry(entry)
    removed_ids = {entry.entry_id for entry in removed}
    kept = [entry for entry in entries if entry.entry_id not in removed_ids]
    return LogReconciliation(
        added_entries=added,
        removed_entries=removed,
        acknowledged_findings=tuple(acknowledged_findings),
        open_entries=tuple(
            entry
            for entry in (*kept, *added)
            if entry.is_open() and entry.unit.file in staged.files
        ),
    )


def _build_unit_keys(
    units: Sequence[AuditableUnit], repository_root: Path, working_directory: Path
) -> dict[UnitKey, AuditableUnit]:
    """Return each unit by its key; one outside the repository is left out."""
    key_to_unit: dict[UnitKey, AuditableUnit] = {}
    for unit in units:
        location = unit.get_location()
        if location is None:
            continue
        file = relate_path_to_repository(
            location.path, repository_root, working_directory
        )
        if file is not None:
            key_to_unit[
                UnitKey(file, describe_unit_name(unit.unit_id, location.path))
            ] = unit
    return key_to_unit


def _build_open_entry(
    identity: FindingIdentity,
    finding: AuditFinding,
    selected_keys: dict[UnitKey, AuditableUnit],
    judge_model_version: str | None,
    flagged_at: str,
) -> AcknowledgementEntry:
    unit = selected_keys.get(UnitKey(identity.file, identity.unit_name))
    location = finding.location
    return AcknowledgementEntry(
        entry_id=identity.build_entry_id(),
        rule_id=identity.rule_id,
        unit=FlaggedUnit(
            file=identity.file,
            kind="unit" if unit is None else unit.unit_type,
            name=identity.unit_name,
            start_line=None if location is None else location.start_line,
            end_line=None if location is None else location.end_line,
        ),
        code_hash=identity.code_hash,
        finding=FlaggedFinding(
            answer=finding.answer.label,
            question=finding.question,
            confidence=finding.confidence,
        ),
        judge_model_version=judge_model_version,
        first_flagged_at=flagged_at,
        status=AcknowledgementStatus.OPEN,
    )
