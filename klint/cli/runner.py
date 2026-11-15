"""What the klint commands share: running the audit and printing the result."""

import json
import sys
from collections.abc import Sequence
from pathlib import Path

from klint.app.audit_json import convert_audit_outcome_to_dict
from klint.app.pipeline import AuditPipeline, AuditRequest
from klint.app.staged_change import StagedChangeScope, read_staged_change_scope
from klint.cli.audit_command import AuditCommand
from klint.cli.command_arguments import CommandArguments, parse_command_arguments
from klint.cli.console import (
    print_error_line,
    print_klint_warnings_raised_inside,
    print_warning_line,
)
from klint.cli.exit_code import ExitCode
from klint.cli.formatter import (
    AuditProgressReporter,
    TerminalScanProgressListener,
    format_applied_rule_exclusions,
    format_audit_report,
)
from klint.cli.judge_usage_description import print_judge_usage_lines
from klint.cli.staged_diff import describe_staged_change
from klint.core.interfaces import BaseAuditProgressListener
from klint.core.models.audits import AuditInput, DiskPathInput
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
        staged: StagedChangeScope | None = None
        audit_input: AuditInput
        if arguments.diff_units is not None:
            try:
                staged = await read_staged_change_scope(
                    arguments.diff_units, Path.cwd()
                )
            except ValueError as exc:
                print_error_line(command, exc)
                return ExitCode.RUN_ERROR
            if not staged.has_files():
                print(f"[{command.name}] No staged change to audit", file=sys.stderr)
            for path in staged.paths_with_unstaged_edits:
                print_warning_line(
                    command,
                    f"'{path}' has unstaged edits too: its units are read from the "
                    "working tree, and the changed lines from the index",
                )
            audit_input = staged.scope.audit_input
        elif arguments.target is not None:
            audit_input = DiskPathInput(path=arguments.target)
        else:
            raise ValueError("A path to audit, or --diff, is required")
        request = AuditRequest(
            audit_input=audit_input,
            audit_kind_id=command.audit_kind_id,
            custom_rule_source=(
                None
                if arguments.custom_rules_path is None
                else JsonFileRuleSource(
                    path=arguments.custom_rules_path.resolve(), is_required=True
                )
            ),
            min_confidence=arguments.min_confidence,
            unit_selector=None if staged is None else staged.scope.unit_selector,
            scan_progress_listener=TerminalScanProgressListener(
                enabled=should_show_progress
            ),
            audit_progress_listener=_ProgressListener(progress, command.name),
        )
        try:
            with print_klint_warnings_raised_inside(command):
                outcome = await self._audit_pipeline.run_audit(request)
        except (OSError, ValueError) as exc:
            # The audit cannot run, for example the target or a rules file
            # cannot be used.
            print_error_line(command, exc)
            return ExitCode.RUN_ERROR
        progress.finish()

        report = outcome.report
        selected_unit_count = len(outcome.selected_unit_ids)
        if selected_unit_count and not report.list_audited_unit_ids():
            # Each unit's failure has had its own line; nothing was checked.
            print_error_line(
                command,
                f"None of the {selected_unit_count} unit(s) to audit could be audited",
            )
            return ExitCode.RUN_ERROR
        findings = report.select_findings(
            should_include_non_problems=arguments.should_show_all_answers,
            min_confidence=arguments.min_confidence,
        )
        if arguments.should_print_json:
            json_report = convert_audit_outcome_to_dict(
                outcome, findings, command.audited_units_json_key, staged
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
        # The report is flushed first, so that the lines on stderr come after
        # it where both streams go to one place, such as a CI log.
        sys.stdout.flush()
        if staged is not None:
            description = describe_staged_change(
                staged, outcome.extracted_unit_count, outcome.selected_unit_count
            )
            print(f"[{command.name}] Staged change: {description}", file=sys.stderr)
        print_judge_usage_lines(command.name, report.get_judge_usage())
        failures = report.select_findings(min_confidence=arguments.min_confidence)
        return ExitCode.PROBLEMS_FOUND if failures else ExitCode.NO_PROBLEMS
