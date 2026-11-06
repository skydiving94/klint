"""The hook's command line: its options, and the lines it prints on stderr."""

import argparse
import contextlib
import sys
import warnings
from collections.abc import Iterator, Sequence
from typing import TextIO

from klint.cli.change_summary_stop_hook.hook_messages import SUMMARIES_PATH
from klint.core import KlintWarning

STOP_HOOK_COMMAND_NAME = "klint-change-summary-stop-hook"


def parse_min_confidence(argv: Sequence[str]) -> float:
    """Return the --min-confidence ``argv`` gives. Raises ValueError for bad options."""
    parser = argparse.ArgumentParser(
        prog=STOP_HOOK_COMMAND_NAME,
        description=(
            "Claude Code Stop hook: lets the agent stop once klint passes its "
            f"summaries of the uncommitted change in {SUMMARIES_PATH}. Reads the "
            "Stop event on stdin, prints its answer as JSON, and exits 0."
        ),
    )
    parser.add_argument(
        "--min-confidence",
        type=float,
        default=0.0,
        help="Minimum confidence (0.0 to 1.0) a failure needs to block the stop",
    )
    try:
        return float(parser.parse_args(argv).min_confidence)
    except SystemExit as error:
        raise ValueError(f"The hook's options {list(argv)} are not valid") from error


def print_hook_line(message: str) -> None:
    """Print one line on stderr, where Claude Code's debug log shows it."""
    print(f"[{STOP_HOOK_COMMAND_NAME}] {message}", file=sys.stderr)


@contextlib.contextmanager
def print_klint_warnings_raised_inside() -> Iterator[None]:
    """Print each KlintWarning raised inside the block as a line on stderr.

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
                print_hook_line(f"Warning: {message}")
            else:
                show_other_warning(message, category, filename, lineno, file, line)

        warnings.showwarning = show_warning
        yield
