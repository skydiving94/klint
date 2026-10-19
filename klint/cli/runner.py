"""What the klint commands share: arguments, running the audit, printing the result."""

import argparse
import asyncio
import json
import sys
import warnings
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import TextIO

from klint.app.audit_mode import AuditMode
from klint.app.audit_pipeline import AuditPipeline, AuditRequest
from klint.app.settings import AppSettings
from klint.app.wiring import create_injector
from klint.cli.formatter import (
    AuditProgressReporter,
    TerminalScanProgressListener,
    format_audit_report,
)
from klint.core.interfaces.audit_progress_listener import BaseAuditProgressListener
from klint.core.klint_warning import KlintWarning


@dataclass(frozen=True)
class AuditCommand:
    """One klint command: its wording, its path argument and the audit it runs.

    name is what the user types and description is shown in the help.
    target_argument_name and target_argument_help describe the path to audit.
    audit_mode is the kind of audit the command asks for, and json_key is the
    key the audited units are listed under in JSON output.
    """

    name: str
    description: str
    target_argument_name: str
    target_argument_help: str
    audit_mode: AuditMode
    json_key: str


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


def print_error_line(command: AuditCommand, error: Exception) -> None:
    """Print one line on stderr saying why the command stopped."""
    print(f"[{command.name}] Error: {error}", file=sys.stderr)


def print_warning_line(command: AuditCommand, message: str) -> None:
    """Print one line on stderr about something ignored; the command goes on."""
    print(f"[{command.name}] Warning: {message}", file=sys.stderr)


@contextmanager
def _print_klint_warnings_raised_inside(command: AuditCommand) -> Iterator[None]:
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
) -> argparse.Namespace:
    """Parse a command line for ``command``; the path to audit is read as ``target``."""
    parser = argparse.ArgumentParser(description=command.description)
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
        "--all",
        action="store_true",
        help=(
            "Output all judgments (Pass, Fail, Irrelevant, Lack of Evidence) "
            "instead of fails only"
        ),
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
    return parser.parse_args(argv)


async def run_audit_command(
    audit_pipeline: AuditPipeline,
    command: AuditCommand,
    target: Path,
    rules_source: Path | None,
    show_all: bool,
    min_confidence: float,
    as_json: bool,
) -> int:
    progress = AuditProgressReporter(enabled=not as_json)
    request = AuditRequest(
        target=target,
        audit_mode=command.audit_mode,
        custom_rules_source=rules_source,
        scan_progress_listener=TerminalScanProgressListener(enabled=not as_json),
        audit_progress_listener=_ProgressListener(progress, command.name),
    )
    try:
        with _print_klint_warnings_raised_inside(command):
            outcome = await audit_pipeline.run_audit(request)
    except (FileNotFoundError, ValueError) as exc:
        print_error_line(command, exc)
        return 1
    progress.finish()

    report = outcome.report
    findings = report.get_findings(
        fails_only=not show_all, min_confidence=min_confidence
    )
    if as_json:
        issues = [finding.to_dict() for finding in findings]
        print(
            json.dumps(
                {command.json_key: report.audited_unit_ids(), "issues": issues},
                indent=2,
            )
        )
    else:
        print(
            format_audit_report(
                findings,
                scanned_file_count=outcome.scanned_file_count,
                audited_unit_count=len(outcome.selected_unit_ids),
            )
        )
    return 0


class AuditCommandApp:
    """Runs one command with an audit pipeline already built."""

    def __init__(
        self,
        command: AuditCommand,
        audit_pipeline: AuditPipeline,
        default_custom_rules: Path | None = None,
    ) -> None:
        self._command = command
        self._audit_pipeline = audit_pipeline
        self._default_custom_rules = default_custom_rules

    async def run(self, argv: Sequence[str] | None = None) -> int:
        args = parse_command_arguments(self._command, argv)
        return await run_audit_command(
            self._audit_pipeline,
            self._command,
            target=args.target,
            rules_source=args.rules or self._default_custom_rules,
            show_all=args.all,
            min_confidence=args.min_confidence,
            as_json=args.json,
        )


async def run_command_from_shell(command: AuditCommand) -> int:
    """Run ``command`` with the arguments the shell passed; return the exit code."""
    argv = sys.argv[1:]
    args = parse_command_arguments(command, argv)
    try:
        with _print_klint_warnings_raised_inside(command):
            settings = await asyncio.to_thread(
                AppSettings.from_env, args.target, args.rules
            )
            injector = create_injector(settings)
            audit_pipeline = injector.get(AuditPipeline)
    except (OSError, ValueError) as error:
        # The command cannot be set up, for example a config or data file is
        # not valid.
        print_error_line(command, error)
        return 1
    app = AuditCommandApp(
        command,
        audit_pipeline,
        default_custom_rules=settings.discovered_config_path,
    )
    return await app.run(argv)
