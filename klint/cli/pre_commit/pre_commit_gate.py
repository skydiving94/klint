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
from dataclasses import dataclass
from pathlib import Path

from klint.app import AppSettings, BindingOverride
from klint.app.acknowledgements import (
    AcknowledgementScope,
    LogReconciliation,
    open_acknowledgement_log,
)
from klint.app.commit_threshold import find_default_commit_threshold
from klint.app.pipeline import AuditOutcome, AuditPipeline, AuditRequest
from klint.app.staged_change import StagedChangeScope, read_staged_change_scope
from klint.app.wiring import AuditingJudge
from klint.catalog.code import FILE_CONTENTS_KIND_ID
from klint.cli.console import (
    print_error_line,
    print_klint_warnings_raised_inside,
    print_warning_line,
)
from klint.cli.exit_code import ExitCode
from klint.cli.judge_usage_description import print_judge_usage_lines
from klint.cli.pre_commit.gate_arguments import (
    PRE_COMMIT_COMMAND,
    GateArguments,
    parse_gate_arguments,
)
from klint.cli.pre_commit.gate_log import reconcile_staged_log, stage_log_changes
from klint.cli.pre_commit.gate_messages import (
    describe_threshold,
    format_blocked_message,
    format_passed_message,
)
from klint.cli.unit_failure_listener import UnitFailureListener
from klint.composition import create_built_in_injector


@dataclass(frozen=True)
class _GateSetup:
    """What one run of the gate works with, once it is set up.

    min_confidence is the least confidence a failure needs to block.
    """

    settings: AppSettings
    arguments: GateArguments
    audit_pipeline: AuditPipeline
    judge: AuditingJudge
    min_confidence: float


class PreCommitGate:
    """Decides whether the staged change may be committed.

    The judge and the rest are wired as for the klint commands; binding
    overrides replace or add bindings.
    """

    def __init__(self, *binding_overrides: BindingOverride) -> None:
        self._binding_overrides = binding_overrides

    async def run(self, argv: Sequence[str]) -> ExitCode:
        """Check the staged change of the working directory's repository."""
        setup = await self._set_up(argv)
        if setup is None:
            return ExitCode.RUN_ERROR
        staged = await _read_staged_change(setup.arguments)
        if staged is None:
            return ExitCode.RUN_ERROR
        if not staged.has_files():
            print(
                f"[{PRE_COMMIT_COMMAND.name}] Nothing is staged, so there is "
                "nothing to check"
            )
            return ExitCode.NO_PROBLEMS
        _warn_about_unstaged_edits(staged)
        outcome = await _audit_staged_change(setup, staged)
        if outcome is None:
            return ExitCode.RUN_ERROR
        reconciliation = await _reconcile_log_with_outcome(setup, staged, outcome)
        if reconciliation is None:
            return ExitCode.RUN_ERROR
        await stage_log_changes(reconciliation, staged.scope.audit_input.root)
        return _report_decision(reconciliation, outcome, setup)

    async def _set_up(self, argv: Sequence[str]) -> _GateSetup | None:
        """Read the command line and the settings, and wire the audit.

        Prints the error and returns None when the gate cannot be set up.
        """
        try:
            with print_klint_warnings_raised_inside(PRE_COMMIT_COMMAND):
                arguments = parse_gate_arguments(PRE_COMMIT_COMMAND, argv)
                settings = await asyncio.to_thread(AppSettings.from_env)
                injector = create_built_in_injector(settings, *self._binding_overrides)
                audit_pipeline = injector.get(AuditPipeline)
                judge = injector.get(AuditingJudge)
        except (OSError, ValueError) as error:
            print_error_line(PRE_COMMIT_COMMAND, error)
            return None
        print(
            f"[{PRE_COMMIT_COMMAND.name}] Judge: {settings.describe_judge()}",
            file=sys.stderr,
        )
        return _GateSetup(
            settings=settings,
            arguments=arguments,
            audit_pipeline=audit_pipeline,
            judge=judge,
            min_confidence=_choose_min_confidence(arguments, settings),
        )


async def _read_staged_change(arguments: GateArguments) -> StagedChangeScope | None:
    """Return the staged change; print the error and return None if unreadable."""
    try:
        return await read_staged_change_scope(arguments.diff_units, Path.cwd())
    except ValueError as error:
        print_error_line(PRE_COMMIT_COMMAND, error)
        return None


def _warn_about_unstaged_edits(staged: StagedChangeScope) -> None:
    for path in staged.paths_with_unstaged_edits:
        print_warning_line(
            PRE_COMMIT_COMMAND,
            f"'{path}' has unstaged edits too: its units are read from the "
            "working tree, and the changed lines from the index",
        )


async def _audit_staged_change(
    setup: _GateSetup, staged: StagedChangeScope
) -> AuditOutcome | None:
    """Audit the staged change, leaving out what the log acknowledges.

    Prints the error and returns None when the audit cannot run, or when a
    unit of the change could not be checked.
    """
    listener = UnitFailureListener()
    repository_root = staged.scope.audit_input.root
    request = AuditRequest(
        audit_input=staged.scope.audit_input,
        audit_kind_id=FILE_CONTENTS_KIND_ID,
        min_confidence=setup.min_confidence,
        unit_selector=staged.scope.unit_selector,
        acknowledgements=AcknowledgementScope(
            open_acknowledgement_log(repository_root), repository_root, Path.cwd()
        ),
        audit_progress_listener=listener,
    )
    try:
        with print_klint_warnings_raised_inside(PRE_COMMIT_COMMAND):
            outcome = await setup.audit_pipeline.run_audit(request)
    except (OSError, ValueError) as error:
        print_error_line(PRE_COMMIT_COMMAND, error)
        return None
    print_judge_usage_lines(PRE_COMMIT_COMMAND.name, outcome.report.get_judge_usage())
    unchecked = listener.describe_failures(len(outcome.selected_unit_ids))
    if unchecked is not None:
        print_error_line(
            PRE_COMMIT_COMMAND, f"the staged change could not be checked: {unchecked}"
        )
        return None
    return outcome


async def _reconcile_log_with_outcome(
    setup: _GateSetup, staged: StagedChangeScope, outcome: AuditOutcome
) -> LogReconciliation | None:
    """Bring the log up to date with the findings on the staged change.

    Prints the error and returns None when the log cannot be read.
    """
    try:
        return reconcile_staged_log(
            staged,
            outcome,
            setup.min_confidence,
            await setup.judge.resolve_model_version(),
        )
    except ValueError as error:
        print_error_line(PRE_COMMIT_COMMAND, error)
        return None


def run_pre_commit_gate() -> int:
    return asyncio.run(PreCommitGate().run(sys.argv[1:]))


def _choose_min_confidence(arguments: GateArguments, settings: AppSettings) -> float:
    """Return the threshold: the command line's, the project's, else the judge's."""
    if arguments.min_confidence is not None:
        return arguments.min_confidence
    if settings.commit_min_confidence is not None:
        return settings.commit_min_confidence
    return find_default_commit_threshold(settings.model_name)


def _report_decision(
    reconciliation: LogReconciliation, outcome: AuditOutcome, setup: _GateSetup
) -> ExitCode:
    """Print whether the commit may go ahead, and return the exit code saying so."""
    threshold_description = describe_threshold(
        setup.min_confidence, setup.settings.model_name
    )
    if reconciliation.open_entries:
        message = format_blocked_message(reconciliation, threshold_description)
        exit_code = ExitCode.PROBLEMS_FOUND
    else:
        message = format_passed_message(
            reconciliation, len(outcome.selected_unit_ids), threshold_description
        )
        exit_code = ExitCode.NO_PROBLEMS
    print(f"[{PRE_COMMIT_COMMAND.name}] {message}")
    return exit_code
