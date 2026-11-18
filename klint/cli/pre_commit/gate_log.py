"""Keeping the acknowledgement log in step with the gate's audit of a change."""

from pathlib import Path

from klint.app.acknowledgements import (
    AcknowledgedFinding,
    LogReconciliation,
    StagedUnits,
    format_timestamp_now,
    open_acknowledgement_log,
    reconcile_log,
    relate_path_to_repository,
)
from klint.app.pipeline import AuditOutcome
from klint.app.staged_change import StagedChangeScope
from klint.catalog.domain_neutral.git.git_command import run_git
from klint.cli.console import print_warning_line
from klint.cli.pre_commit.gate_arguments import PRE_COMMIT_COMMAND


def reconcile_staged_log(
    staged: StagedChangeScope,
    outcome: AuditOutcome,
    min_confidence: float,
    model_version: str | None,
) -> LogReconciliation:
    """Bring the log up to date with the findings ``outcome`` holds on ``staged``.

    Raises ValueError when an entry of the log cannot be read.
    """
    repository_root = staged.scope.audit_input.root
    return reconcile_log(
        open_acknowledgement_log(repository_root),
        outcome.report.select_findings(min_confidence=min_confidence),
        _select_acknowledged(outcome, min_confidence),
        _list_staged_units(staged, repository_root),
        repository_root,
        Path.cwd(),
        model_version,
        format_timestamp_now(),
    )


def _select_acknowledged(
    outcome: AuditOutcome, min_confidence: float
) -> list[AcknowledgedFinding]:
    """Return the acknowledged findings that would have blocked the commit."""
    return [
        acknowledged
        for acknowledged in outcome.acknowledged_findings
        if acknowledged.finding.is_problem()
        and acknowledged.finding.does_meet_confidence(min_confidence)
    ]


def _list_staged_units(staged: StagedChangeScope, repository_root: Path) -> StagedUnits:
    """Return what the staged change holds, its files from the repository's root."""
    audited_files = (
        relate_path_to_repository(path, repository_root, Path.cwd())
        for path in staged.scope.list_audited_paths()
    )
    selector = staged.scope.unit_selector
    return StagedUnits(
        files=frozenset(
            (
                *(file for file in audited_files if file is not None),
                *staged.scope.deleted_paths,
            )
        ),
        selected_units=selector.selected_units,
        offered_units=selector.offered_units,
    )


async def stage_log_changes(
    reconciliation: LogReconciliation, repository_root: Path
) -> None:
    """Stage each entry file written or removed, so the commit carries the log.

    A failure to stage is printed as a warning; the gate goes on.
    """
    if not reconciliation.did_change_log():
        return
    log = open_acknowledgement_log(repository_root)
    paths = [
        str(log.locate_entry(entry.entry_id).relative_to(repository_root))
        for entry in (*reconciliation.added_entries, *reconciliation.removed_entries)
    ]
    try:
        output = await run_git(["add", "-A", "--", *paths], repository_root)
    except ValueError as error:
        print_warning_line(PRE_COMMIT_COMMAND, f"the log could not be staged: {error}")
        return
    if output.return_code != 0:
        print_warning_line(
            PRE_COMMIT_COMMAND, f"the log could not be staged: {output.stderr.strip()}"
        )
