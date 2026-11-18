"""The command line of a klint command, and how it is parsed."""

import argparse
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from klint.catalog.domain_neutral.git import DiffUnits
from klint.cli.audit_command import AuditCommand, DiffOptions
from klint.cli.exit_code import ExitCode
from klint.core import describe_removed_name


@dataclass(frozen=True)
class CommandArguments:
    """A command line, parsed.

    target is the path to audit, and custom_rules_path the file given with
    --rules. should_show_all_answers asks for every answer instead of failures
    only, and min_confidence is the least confidence a finding needs to be
    reported. should_print_json asks for JSON instead of the terminal report.
    diff_units is the choice --diff-units makes when --diff or --diff-from
    is given; None without them, when target is the path to audit, and for
    a command without --diff-units.
    diff_from is the file --diff-from reads the diff from, "-" for stdin;
    None without --diff-from.
    """

    target: Path | None
    custom_rules_path: Path | None
    should_show_all_answers: bool
    min_confidence: float
    should_print_json: bool
    diff_units: DiffUnits | None = None
    diff_from: Path | None = None


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
        nargs=None if command.diff_options is DiffOptions.NONE else "?",
        help=command.target_argument_help,
    )
    match command.diff_options:
        case DiffOptions.CHANGED_UNITS:
            _add_diff_arguments(parser)
        case DiffOptions.CHANGED_DIRECTORIES:
            _add_diff_from_directories_argument(parser)
        case DiffOptions.NONE:
            pass
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
        dest="is_removed_all_given",
        help=argparse.SUPPRESS,
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
    if namespace.is_removed_all_given:
        # Defined only to refuse it: argparse would take it as --all-answers.
        parser.error(describe_removed_name("--all", "--all-answers"))
    diff_units = None
    diff_from = None
    match command.diff_options:
        case DiffOptions.CHANGED_UNITS:
            diff_units = _read_diff_units(parser, namespace)
            diff_from = namespace.diff_from
        case DiffOptions.CHANGED_DIRECTORIES:
            diff_from = _read_diff_from_without_units(parser, namespace)
        case DiffOptions.NONE:
            pass
    return CommandArguments(
        target=namespace.target,
        custom_rules_path=namespace.rules,
        should_show_all_answers=namespace.all_answers,
        min_confidence=namespace.min_confidence,
        should_print_json=namespace.json,
        diff_units=diff_units,
        diff_from=diff_from,
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
        "--diff-from",
        type=Path,
        default=None,
        metavar="FILE",
        help=(
            "Audit what a unified diff in git's format touches instead of a "
            "path, such as 'git diff main...HEAD' writes; '-' reads it from "
            "stdin. Its paths are taken as relative to the current directory, "
            "and the files there must be the ones the diff's index lines name"
        ),
    )
    parser.add_argument(
        "--diff-units",
        type=DiffUnits,
        choices=list(DiffUnits),
        default=None,
        help=(
            "With --diff or --diff-from, which units of each changed file to "
            "audit: 'units' (the default) for the file and every function and "
            "class on a changed line, 'file' for the file alone, 'all' for every unit"
        ),
    )


def _add_diff_from_directories_argument(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--diff-from",
        type=Path,
        default=None,
        metavar="FILE",
        help=(
            "Audit, instead of a path, each directory that holds a file a "
            "unified diff in git's format touches, such as 'git diff "
            "main...HEAD' writes, and each of its parents; '-' reads it from "
            "stdin. The project is the current directory: the diff's paths are "
            "taken as relative to it, and the files there must be the ones the "
            "diff's index lines name"
        ),
    )


def _read_diff_from_without_units(
    parser: argparse.ArgumentParser, namespace: argparse.Namespace
) -> Path | None:
    """Return the file --diff-from names; None without it. Exits on a clash."""
    diff_from: Path | None = namespace.diff_from
    if diff_from is not None and namespace.target is not None:
        parser.error("--diff-from takes no path: the project is the current directory")
    if diff_from is None and namespace.target is None:
        parser.error("a path to audit or --diff-from is required")
    return diff_from


def _read_diff_units(
    parser: argparse.ArgumentParser, namespace: argparse.Namespace
) -> DiffUnits | None:
    """Return the units a diff option asks for; None without one. Exits on a clash."""
    if namespace.diff and namespace.diff_from is not None:
        parser.error("--diff and --diff-from are two kinds of change: give one")
    if namespace.diff or namespace.diff_from is not None:
        if namespace.target is not None and namespace.diff:
            parser.error("--diff takes no path: it audits the staged change")
        if namespace.target is not None:
            parser.error("--diff-from takes no path: it audits the files of the diff")
        return namespace.diff_units or DiffUnits.UNITS
    if namespace.diff_units is not None:
        parser.error("--diff-units needs --diff or --diff-from")
    if namespace.target is None:
        parser.error("a path to audit, --diff or --diff-from is required")
    return None
