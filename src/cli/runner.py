"""What the klint commands share: arguments, running the audit, printing the result."""

import argparse
import asyncio
import json
import sys
import warnings
from collections.abc import Callable, Iterator, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

from src.app.settings import AppSettings
from src.app.usecases.audit_path import AuditPath
from src.cli.formatter import AuditProgressReporter, format_audit_report
from src.core.klint_warning import KlintWarning


@dataclass(frozen=True)
class AuditCommand:
    """One klint command: its wording, its path argument and the audit it runs.

    name is what the user types and description is shown in the help.
    target_argument_name and target_argument_help describe the path to audit.
    target_label is the word for what was audited in the output, and json_key
    is the key the audited paths are listed under in JSON output.
    """

    name: str
    description: str
    target_argument_name: str
    target_argument_help: str
    target_label: str
    json_key: str
    create_audit_path: Callable[[AppSettings], AuditPath]


class _ProgressListener:
    """Advances the progress bar and reports skipped targets on stderr."""

    def __init__(self, progress: AuditProgressReporter, command_name: str) -> None:
        self._progress = progress
        self._command_name = command_name

    def target_failed(self, name: str, error: Exception) -> None:
        self._progress.finish()
        print(f"[{self._command_name}] Skipping {name}: {error}", file=sys.stderr)

    def target_done(self, name: str) -> None:
        self._progress.advance(name)


def print_error_line(command: AuditCommand, error: Exception) -> None:
    """Print one line on stderr saying why the command stopped."""
    print(f"[{command.name}] Error: {error}", file=sys.stderr)


def print_warning_line(command: AuditCommand, message: str) -> None:
    """Print one line on stderr about something ignored; the command goes on."""
    print(f"[{command.name}] Warning: {message}", file=sys.stderr)


@contextmanager
def _print_klint_warnings_raised_inside(command: AuditCommand) -> Iterator[None]:
    """Print each KlintWarning raised inside the block as one line.

    Any other warning raised inside is passed on unchanged afterwards.
    """
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always", KlintWarning)
        try:
            yield
        finally:
            for warning in caught:
                if issubclass(warning.category, KlintWarning):
                    print_warning_line(command, str(warning.message))
    for warning in caught:
        if not issubclass(warning.category, KlintWarning):
            warnings.warn_explicit(
                warning.message, warning.category, warning.filename, warning.lineno
            )


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
    audit_path: AuditPath,
    command: AuditCommand,
    target: Path,
    rules_source: Path | None,
    show_all: bool,
    min_confidence: float,
    as_json: bool,
) -> int:
    try:
        with _print_klint_warnings_raised_inside(command):
            plan = await audit_path.prepare(target, rules_source)
    except (FileNotFoundError, ValueError, json.JSONDecodeError) as exc:
        print_error_line(command, exc)
        return 1

    progress = AuditProgressReporter(
        total=len(plan.targets), label=command.target_label, enabled=not as_json
    )
    progress.start()
    result = await audit_path.run(
        plan,
        fails_only=not show_all,
        min_confidence=min_confidence,
        listener=_ProgressListener(progress, command.name),
    )
    progress.finish()

    if as_json:
        issues = [finding.to_dict() for finding in result.findings]
        print(
            json.dumps({command.json_key: result.examined, "issues": issues}, indent=2)
        )
    else:
        print(
            format_audit_report(
                result.examined, result.findings, target_label=command.target_label
            )
        )
    return 0


class AuditCommandApp:
    """Runs one command against an audit path that is already built."""

    def __init__(
        self,
        command: AuditCommand,
        audit_path: AuditPath,
        default_custom_rules: Path | None = None,
    ) -> None:
        self._command = command
        self._audit_path = audit_path
        self._default_custom_rules = default_custom_rules

    async def run(self, argv: Sequence[str] | None = None) -> int:
        args = parse_command_arguments(self._command, argv)
        return await run_audit_command(
            self._audit_path,
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
            audit_path = command.create_audit_path(settings)
    except (OSError, ValueError) as error:
        # The command cannot be set up, for example a config or data file is
        # not valid.
        print_error_line(command, error)
        return 1
    app = AuditCommandApp(
        command, audit_path, default_custom_rules=settings.discovered_config_path
    )
    return await app.run(argv)
