"""The command line of klint-pre-commit."""

import argparse
from collections.abc import Sequence
from dataclasses import dataclass

from klint.catalog.domain_neutral.git import DiffUnits
from klint.cli.audit_command import AuditCommand
from klint.cli.exit_code import ExitCode


@dataclass(frozen=True)
class GateArguments:
    """What klint-pre-commit was asked.

    min_confidence is the threshold given on the command line; None leaves
    it to the project's setting, else to the judge in use. diff_units is
    the choice of units in each changed file.
    """

    min_confidence: float | None
    diff_units: DiffUnits


def parse_gate_arguments(
    command: AuditCommand, argv: Sequence[str] | None = None
) -> GateArguments:
    """Parse the command line of klint-pre-commit."""
    parser = argparse.ArgumentParser(
        prog=command.name,
        description=command.description,
        epilog=(
            f"Exit status: {ExitCode.NO_PROBLEMS.value} when the commit may go "
            f"ahead, {ExitCode.PROBLEMS_FOUND.value} when an open finding blocks "
            f"it, {ExitCode.RUN_ERROR.value} when klint cannot check the change, "
            "as when the judge is down. git commit --no-verify skips the check."
        ),
    )
    parser.add_argument(
        "--min-confidence",
        type=float,
        default=None,
        help=(
            "Least confidence (0.0 to 1.0) a failure needs to block the commit; "
            "by default the project's KLINT_COMMIT_MIN_CONFIDENCE, else the "
            "judge's own: 0.8 for Jev, 0.5 for Kev"
        ),
    )
    parser.add_argument(
        "--diff-units",
        type=DiffUnits,
        choices=list(DiffUnits),
        default=DiffUnits.UNITS,
        help=(
            "Which units of each changed file to check: 'units' (the default) "
            "for the file and every function and class on a changed line, "
            "'file' for the file alone, 'all' for every unit"
        ),
    )
    namespace = parser.parse_args(argv)
    return GateArguments(
        min_confidence=namespace.min_confidence, diff_units=namespace.diff_units
    )
