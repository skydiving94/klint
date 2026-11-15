"""What the klint commands share: running the audit and printing the result."""

import json
import sys
from collections.abc import Sequence
from pathlib import Path

from klint.app.acknowledgements import find_acknowledgement_scope
from klint.app.audit_json import convert_audit_outcome_to_dict
from klint.app.pipeline import AuditOutcome, AuditPipeline, AuditRequest
from klint.cli.audit_command import AuditCommand
from klint.cli.audit_input_choice import ChosenAuditInput, choose_audit_input
from klint.cli.command_arguments import CommandArguments, parse_command_arguments
from klint.cli.console import print_error_line, print_klint_warnings_raised_inside
from klint.cli.exit_code import ExitCode
from klint.cli.formatter import (
    AuditProgressReporter,
    TerminalScanProgressListener,
    format_applied_rule_exclusions,
    format_audit_report,
)
from klint.cli.judge_usage_description import print_judge_usage_lines
from klint.cli.pre_commit import format_acknowledged_findings
from klint.cli.staged_diff import describe_staged_change
from klint.core.interfaces import BaseAuditProgressListener
from klint.infra.rule_loader import JsonFileRuleSource


class _ProgressListener(BaseAuditProgressListener):
    """Advances the progress bar and reports skipped units on stderr."""

    def __init__(self, progress: AuditProgressReporter, command_name: str) -> None:
        self._progress = progress
        self._command_name = command_name

    def report_audit_started(self, unit_count: int) -> None:
        self._progress.start(unit_count)

    def report_unit_audited(self, unit_id: str) -> None:
        self._progress.advance(unit_id)

    def report_unit_failed(self, unit_id: str, error: Exception) -> None:
        self._progress.finish()
        print(f"[{self._command_name}] Skipping {unit_id}: {error}", file=sys.stderr)
        self._progress.advance(unit_id)


class AuditCommandApp:
    """Runs one command with an audit pipeline already built."""

    def __init__(
        self,
        command: AuditCommand,
        audit_pipeline: AuditPipeline,
    ) -> None:
        self._command = command
        self._audit_pipeline = audit_pipeline

    async def run(self, argv: Sequence[str] | None = None) -> ExitCode:
        """Parse ``argv`` and run the command; return the exit code."""
        with print_klint_warnings_raised_inside(self._command):
            arguments = parse_command_arguments(self._command, argv)
        return await self.run_with_arguments(arguments)

    async def run_with_arguments(self, arguments: CommandArguments) -> ExitCode:
        """Run the command on a parsed command line; return the exit code."""
        command = self._command
        should_show_progress = not arguments.should_print_json
        progress = AuditProgressReporter(enabled=should_show_progress)
        try:
            chosen = await choose_audit_input(command, arguments)
        except ValueError as exc:
            print_error_line(command, exc)
            return ExitCode.RUN_ERROR
        request = await _build_request(command, arguments, chosen, progress)
        try:
            with print_klint_warnings_raised_inside(command):
                outcome = await self._audit_pipeline.run_audit(request)
        except (OSError, ValueError) as exc:
            # The audit cannot run, for example the target or a rules file
            # cannot be used.
            print_error_line(command, exc)
            return ExitCode.RUN_ERROR
        progress.finish()
        selected_unit_count = len(outcome.selected_unit_ids)
        if selected_unit_count and not outcome.report.list_audited_unit_ids():
            # Each unit's failure has had its own line; nothing was checked.
            print_error_line(
                command,
                f"None of the {selected_unit_count} unit(s) to audit could be audited",
            )
            return ExitCode.RUN_ERROR
        _print_report(command, arguments, outcome, chosen)
        failures = outcome.report.select_findings(
            min_confidence=arguments.min_confidence
        )
        return ExitCode.PROBLEMS_FOUND if failures else ExitCode.NO_PROBLEMS


async def _build_request(
    command: AuditCommand,
    arguments: CommandArguments,
    chosen: ChosenAuditInput,
    progress: AuditProgressReporter,
) -> AuditRequest:
    """Return the request for the audit ``arguments`` ask for, of ``chosen``."""
    should_show_progress = not arguments.should_print_json
    return AuditRequest(
        audit_input=chosen.audit_input,
        audit_kind_id=command.audit_kind_id,
        custom_rule_source=(
            None
            if arguments.custom_rules_path is None
            else JsonFileRuleSource(
                path=arguments.custom_rules_path.resolve(), is_required=True
            )
        ),
        min_confidence=arguments.min_confidence,
        unit_selector=chosen.find_unit_selector(),
        # The repository's acknowledgement log, when the target is in one.
        acknowledgements=await find_acknowledgement_scope(
            chosen.log_directory, Path.cwd()
        ),
        scan_progress_listener=TerminalScanProgressListener(
            enabled=should_show_progress
        ),
        audit_progress_listener=_ProgressListener(progress, command.name),
    )


def _print_report(
    command: AuditCommand,
    arguments: CommandArguments,
    outcome: AuditOutcome,
    chosen: ChosenAuditInput,
) -> None:
    """Print the report on stdout, then what was audited and the judge's usage."""
    report = outcome.report
    findings = report.select_findings(
        should_include_non_problems=arguments.should_show_all_answers,
        min_confidence=arguments.min_confidence,
    )
    if arguments.should_print_json:
        json_report = convert_audit_outcome_to_dict(
            outcome, findings, command.audited_units_json_key, chosen.staged
        )
        print(json.dumps(json_report, indent=2))
    else:
        print(
            format_audit_report(
                findings,
                scanned_file_count=outcome.scanned_file_count,
                audited_unit_count=len(outcome.selected_unit_ids),
                no_problems_message=command.no_problems_message,
                unit_id_to_roll_up_status=report.map_unit_id_to_roll_up_status(),
            )
        )
        if outcome.applied_rule_exclusions:
            print(format_applied_rule_exclusions(outcome.applied_rule_exclusions))
        if outcome.acknowledged_findings:
            print(format_acknowledged_findings(outcome.acknowledged_findings))
    # The report is flushed first, so that the lines on stderr come after
    # it where both streams go to one place, such as a CI log.
    sys.stdout.flush()
    if chosen.staged is not None:
        description = describe_staged_change(
            chosen.staged, outcome.extracted_unit_count, outcome.selected_unit_count
        )
        print(f"[{command.name}] Staged change: {description}", file=sys.stderr)
    print_judge_usage_lines(command.name, report.get_judge_usage())
