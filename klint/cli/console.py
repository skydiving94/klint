"""The lines a command prints on stderr about its run, apart from the report."""

import sys
import warnings
from collections.abc import Iterator
from contextlib import contextmanager
from typing import TextIO

from klint.cli.audit_command import AuditCommand
from klint.core import KlintWarning


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
