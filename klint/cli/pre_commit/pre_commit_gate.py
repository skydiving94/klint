"""The klint-pre-commit command: a git pre-commit hook on the staged change.

It audits the staged change as klint --diff does, brings the repository's
acknowledgement log up to date with what it finds, stages the log, and
blocks the commit while an open finding remains in the changed files. When
the judge is down or klint cannot run, the commit is blocked too, with the
reason.
"""

import asyncio
import sys
from collections.abc import Sequence
from pathlib import Path

from klint.app import AppSettings, BindingOverride
from klint.app.acknowledgements import (
    LogReconciliation,
    StagedUnits,
    format_timestamp_now,
    open_acknowledgement_log,
    reconcile_log,
    relate_path_to_repository,
)
from klint.app.commit_threshold import find_default_commit_threshold
from klint.app.pipeline import AuditOutcome, AuditPipeline, AuditRequest
from klint.app.staged_change import StagedChangeScope, read_staged_change_scope
from klint.app.wiring import AuditingJudge
from klint.catalog.code import FILE_CONTENTS_KIND_ID
from klint.catalog.domain_neutral.git.git_command import run_git
from klint.cli.audit_command import AuditCommand
from klint.cli.console import (
    print_error_line,
    print_klint_warnings_raised_inside,
    print_warning_line,
)
from klint.cli.exit_code import ExitCode
from klint.cli.judge_usage_description import print_judge_usage_lines
from klint.cli.pre_commit.gate_arguments import GateArguments, parse_gate_arguments
from klint.cli.pre_commit.gate_messages import (
    describe_threshold,
    format_blocked_message,
    format_passed_message,
)
from klint.cli.unit_failure_listener import UnitFailureListener
from klint.composition import create_built_in_injector

PRE_COMMIT_COMMAND = AuditCommand(
    name="klint-pre-commit",
    description=(
        "klint - pre-commit hook: audits the staged change and blocks the commit "
        "while a finding is neither fixed nor acknowledged in the repository's "
        "acknowledgement log"
    ),
    target_argument_name="",
    target_argument_help="",
    audit_kind_id=FILE_CONTENTS_KIND_ID,
    audited_units_json_key="examined_files",
    does_offer_diff=True,
)


class PreCommitGate:
    """Decides whether the staged change may be committed.

    The judge and the rest are wired as for the klint commands; binding
    overrides replace or add bindings.
    """

    def __init__(self, *binding_overrides: BindingOverride) -> None:
        self._binding_overrides = binding_overrides

    async def run(self, argv: Sequence[str]) -> ExitCode:
        """Check the staged change of the working directory's repository."""
        command = PRE_COMMIT_COMMAND
        try:
            with print_klint_warnings_raised_inside(command):
                arguments = parse_gate_arguments(command, argv)
                settings = await asyncio.to_thread(AppSettings.from_env)
                injector = create_built_in_injector(settings, *self._binding_overrides)
                audit_pipeline = injector.get(AuditPipeline)
                judge = injector.get(AuditingJudge)
        except (OSError, ValueError) as error:
            print_error_line(command, error)
            return ExitCode.RUN_ERROR
        print(f"[{command.name}] Judge: {settings.describe_judge()}", file=sys.stderr)
        min_confidence = _choose_min_confidence(arguments, settings)
        try:
            staged = await read_staged_change_scope(arguments.diff_units, Path.cwd())
        except ValueError as error:
            print_error_line(command, error)
            return ExitCode.RUN_ERROR
        if not staged.has_files():
            print(f"[{command.name}] Nothing is staged, so there is nothing to check")
            return ExitCode.NO_PROBLEMS
        for path in staged.paths_with_unstaged_edits:
            print_warning_line(
                command,
                f"'{path}' has unstaged edits too: its units are read from the "
                "working tree, and the changed lines from the index",
            )
        listener = UnitFailureListener()
        request = AuditRequest(
            audit_input=staged.scope.audit_input,
            audit_kind_id=command.audit_kind_id,
            min_confidence=min_confidence,
            unit_selector=staged.scope.unit_selector,
            audit_progress_listener=listener,
        )
        try:
            with print_klint_warnings_raised_inside(command):
                outcome = await audit_pipeline.run_audit(request)
        except (OSError, ValueError) as error:
            print_error_line(command, error)
            return ExitCode.RUN_ERROR
        print_judge_usage_lines(command.name, outcome.report.get_judge_usage())
        unchecked = listener.describe_failures(len(outcome.selected_unit_ids))
        if unchecked is not None:
            print_error_line(
                command, f"the staged change could not be checked: {unchecked}"
            )
            return ExitCode.RUN_ERROR
        repository_root = staged.scope.audit_input.root
        try:
            reconciliation = reconcile_log(
                open_acknowledgement_log(repository_root),
                outcome.report.select_findings(min_confidence=min_confidence),
                _list_staged_units(staged, repository_root),
                repository_root,
                Path.cwd(),
                await judge.resolve_model_version(),
                format_timestamp_now(),
            )
        except ValueError as error:
            print_error_line(command, error)
            return ExitCode.RUN_ERROR
        await _stage_log_changes(command, reconciliation, repository_root)
        return _report_decision(
            command, reconciliation, outcome, min_confidence, settings
        )


def run_pre_commit_gate() -> int:
    return asyncio.run(PreCommitGate().run(sys.argv[1:]))


def _choose_min_confidence(arguments: GateArguments, settings: AppSettings) -> float:
    """Return the threshold: the command line's, the project's, else the judge's."""
    if arguments.min_confidence is not None:
        return arguments.min_confidence
    if settings.commit_min_confidence is not None:
        return settings.commit_min_confidence
    return find_default_commit_threshold(settings.model_name)


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


async def _stage_log_changes(
    command: AuditCommand, reconciliation: LogReconciliation, repository_root: Path
) -> None:
    """Stage each entry file written or removed, so the commit carries the log."""
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
        print_warning_line(command, f"the log could not be staged: {error}")
        return
    if output.return_code != 0:
        print_warning_line(
            command, f"the log could not be staged: {output.stderr.strip()}"
        )


def _report_decision(
    command: AuditCommand,
    reconciliation: LogReconciliation,
    outcome: AuditOutcome,
    min_confidence: float,
    settings: AppSettings,
) -> ExitCode:
    threshold_description = describe_threshold(min_confidence, settings.model_name)
    if reconciliation.open_entries:
        message = format_blocked_message(reconciliation, threshold_description)
        exit_code = ExitCode.PROBLEMS_FOUND
    else:
        message = format_passed_message(
            reconciliation, len(outcome.selected_unit_ids), threshold_description
        )
        exit_code = ExitCode.NO_PROBLEMS
    print(f"[{command.name}] {message}")
    return exit_code
