"""What the klint commands share: arguments, running the audit, printing the result."""

import argparse
import json
import sys
import warnings
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import TextIO

from klint.app.pipeline import AuditPipeline, AuditRequest
from klint.cli.exit_code import ExitCode
from klint.cli.formatter import (
    AuditProgressReporter,
    TerminalScanProgressListener,
    format_applied_rule_exclusions,
    format_audit_report,
)
from klint.cli.judge_usage_description import (
    convert_answer_cache_to_dict,
    convert_judge_usage_to_dict,
    print_judge_usage_lines,
)
from klint.core import KlintWarning, warn_about_deprecated_name
from klint.core.interfaces import BaseAuditProgressListener
from klint.core.models.audits import DiskPathInput
from klint.infra.rule_loader import JsonFileRuleSource


@dataclass(frozen=True)
class AuditCommand:
    """One klint command: its wording, its path argument and the audit it runs.

    name is what the user types and description is shown in the help.
    target_argument_name and target_argument_help describe the path to audit.
    audit_kind_id names the kind of audit the command asks for, and
    audited_units_json_key is the key the audited units are listed under in
    JSON output. The terminal report says no_problems_message when it has no
    finding to show.
    """

    name: str
    description: str
    target_argument_name: str
    target_argument_help: str
    audit_kind_id: str
    audited_units_json_key: str
    no_problems_message: str = "No architectural or semantic issues found."


@dataclass(frozen=True)
class CommandArguments:
    """A command line, parsed.

    target is the path to audit, and custom_rules_path the file given with
    --rules. should_show_all_answers asks for every answer instead of failures
    only, and min_confidence is the least confidence a finding needs to be
    reported. should_print_json asks for JSON instead of the terminal report.
    """

    target: Path
    custom_rules_path: Path | None
    should_show_all_answers: bool
    min_confidence: float
    should_print_json: bool


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


def print_error_line(command: AuditCommand, reason: Exception | str) -> None:
    """Print one line on stderr saying why the command stopped."""
    print(f"[{command.name}] Error: {reason}", file=sys.stderr)


def print_warning_line(command: AuditCommand, message: str) -> None:
    """Print one line on stderr about something ignored; the command goes on."""
    print(f"[{command.name}] Warning: {message}", file=sys.stderr)


@contextmanager
def print_klint_warnings_raised_inside(command: AuditCommand) -> Iterator[None]:
    """Print each KlintWarning raised inside the block as one line, as it is raised.

    Any other warning raised inside is shown as it would be outside the block.
    """
    with warnings.catch_warnings():
        warnings.simplefilter("always", KlintWarning)
        show_other_warning = warnings.showwarning

        def show_warning(
            message: Warning | str,
            category: type[Warning],
            filename: str,
            lineno: int,
            file: TextIO | None = None,
            line: str | None = None,
        ) -> None:
            if issubclass(category, KlintWarning):
                print_warning_line(command, str(message))
            else:
                show_other_warning(message, category, filename, lineno, file, line)

        warnings.showwarning = show_warning
        yield


def parse_command_arguments(
    command: AuditCommand, argv: Sequence[str] | None = None
) -> CommandArguments:
    """Parse a command line for ``command``."""
    parser = argparse.ArgumentParser(
        description=command.description,
        epilog=(
            f"Exit status: {ExitCode.NO_PROBLEMS.value} when no failure is found, "
            f"{ExitCode.PROBLEMS_FOUND.value} when one is, "
            f"{ExitCode.RUN_ERROR.value} when the audit cannot run or no unit "
            "could be audited."
        ),
    )
    parser.add_argument(
        "target",
        metavar=command.target_argument_name,
        type=Path,
        help=command.target_argument_help,
    )
    parser.add_argument(
        "--rules",
        type=Path,
        default=None,
        help="Path to user-defined rules JSON file",
    )
    parser.add_argument(
        "--all-answers",
        action="store_true",
        help="Output every answer, not only the problems",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        dest="all_answers_under_old_name",
        help="Old name of --all-answers, deprecated",
    )
    parser.add_argument(
        "--min-confidence",
        type=float,
        default=0.0,
        help="Minimum confidence threshold (0.0 to 1.0) required to report an issue",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output raw JSON instead of formatted terminal report",
    )
    namespace = parser.parse_args(argv)
    if namespace.all_answers_under_old_name:
        warn_about_deprecated_name("--all", "--all-answers")
    return CommandArguments(
        target=namespace.target,
        custom_rules_path=namespace.rules,
        should_show_all_answers=(
            namespace.all_answers or namespace.all_answers_under_old_name
        ),
        min_confidence=namespace.min_confidence,
        should_print_json=namespace.json,
    )


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
        request = AuditRequest(
            audit_input=DiskPathInput(path=arguments.target),
            audit_kind_id=command.audit_kind_id,
            custom_rule_source=(
                None
                if arguments.custom_rules_path is None
                else JsonFileRuleSource(
                    path=arguments.custom_rules_path.resolve(), is_required=True
                )
            ),
            min_confidence=arguments.min_confidence,
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
            json_report: dict[str, object] = {
                command.audited_units_json_key: report.list_audited_unit_ids(),
                "unit_id_to_roll_up_status": {
                    unit_id: status.value
                    for unit_id, status in (
                        report.map_unit_id_to_roll_up_status().items()
                    )
                },
                "findings": [finding.convert_to_dict() for finding in findings],
                "judge_usage": convert_judge_usage_to_dict(report.get_judge_usage()),
            }
            # Present only when the answer cache took part, so a run without
            # one gets the same JSON as before.
            if report.get_judge_usage().did_cache_take_part():
                json_report["answer_cache"] = convert_answer_cache_to_dict(
                    report.get_judge_usage()
                )
            # Present only when the project's klint.json turned a rule off, so
            # a project without exclusions gets the same JSON as before.
            if outcome.applied_rule_exclusions:
                json_report["applied_rule_exclusions"] = [
                    applied.convert_to_dict()
                    for applied in outcome.applied_rule_exclusions
                ]
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
        print_judge_usage_lines(command.name, report.get_judge_usage())
        failures = report.select_findings(min_confidence=arguments.min_confidence)
        return ExitCode.PROBLEMS_FOUND if failures else ExitCode.NO_PROBLEMS
