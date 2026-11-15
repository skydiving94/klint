"""The command line of a klint command, and how it is parsed."""

import argparse
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from klint.catalog.domain_neutral.git import DiffUnits
from klint.cli.audit_command import AuditCommand
from klint.cli.exit_code import ExitCode
from klint.core import warn_about_deprecated_name


@dataclass(frozen=True)
class CommandArguments:
    """A command line, parsed.

    target is the path to audit, and custom_rules_path the file given with
    --rules. should_show_all_answers asks for every answer instead of failures
    only, and min_confidence is the least confidence a finding needs to be
    reported. should_print_json asks for JSON instead of the terminal report.
    diff_units is the choice --diff-units makes when --diff is given; None
    without --diff, when target is the path to audit.
    """

    target: Path | None
    custom_rules_path: Path | None
    should_show_all_answers: bool
    min_confidence: float
    should_print_json: bool
    diff_units: DiffUnits | None = None


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
        nargs="?" if command.does_offer_diff else None,
        help=command.target_argument_help,
    )
    if command.does_offer_diff:
        _add_diff_arguments(parser)
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
    diff_units = None
    if command.does_offer_diff:
        diff_units = _read_diff_units(parser, namespace)
    return CommandArguments(
        target=namespace.target,
        custom_rules_path=namespace.rules,
        should_show_all_answers=(
            namespace.all_answers or namespace.all_answers_under_old_name
        ),
        min_confidence=namespace.min_confidence,
        should_print_json=namespace.json,
        diff_units=diff_units,
    )


def _add_diff_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--diff",
        action="store_true",
        help=(
            "Audit the staged change of the current directory's git repository "
            "instead of a path: the units the change touches, in the changed files"
        ),
    )
    parser.add_argument(
        "--diff-units",
        type=DiffUnits,
        choices=list(DiffUnits),
        default=None,
        help=(
            "With --diff, which units of each changed file to audit: 'units' "
            "(the default) for the file and every function and class on a "
            "changed line, 'file' for the file alone, 'all' for every unit"
        ),
    )


def _read_diff_units(
    parser: argparse.ArgumentParser, namespace: argparse.Namespace
) -> DiffUnits | None:
    """Return the units --diff asks for; None without --diff. Exits when they clash."""
    if namespace.diff:
        if namespace.target is not None:
            parser.error("--diff takes no path: it audits the staged change")
        return namespace.diff_units or DiffUnits.UNITS
    if namespace.diff_units is not None:
        parser.error("--diff-units needs --diff")
    if namespace.target is None:
        parser.error("a path to audit, or --diff, is required")
    return None
