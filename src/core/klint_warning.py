"""The warning klint raises when it carries on after ignoring something."""

import warnings
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path


class KlintWarning(UserWarning):
    """Something was ignored or left out; the run continues."""


def warn_about_unreadable_directory(path: Path, error: OSError) -> None:
    """Warn that the directory at ``path`` is left out because it cannot be read."""
    _warn(f"Directory '{path}' is left out: it cannot be read ({_reason(error)})")


def warn_about_unreadable_file(path: Path, error: OSError) -> None:
    """Warn that the file at ``path`` is left out because it cannot be read."""
    _warn(f"File '{path}' is left out: it cannot be read ({_reason(error)})")


def warn_about_unprocessable_file(path: Path, error: Exception) -> None:
    """Warn that the file at ``path`` is left out because extracting it failed."""
    _warn(f"File '{path}' is left out: it cannot be processed ({_reason(error)})")


@contextmanager
def leave_out_file_on_failure(path: Path) -> Iterator[None]:
    """Turn a failure to extract the file at ``path`` into a warning.

    An error raised inside the block is not passed on: the file is left out
    and the run goes on. Any error counts, so that one file never stops the
    audit of the others.
    """
    try:
        yield
    except OSError as error:
        warn_about_unreadable_file(path, error)
    except Exception as error:
        warn_about_unprocessable_file(path, error)


def _warn(message: str) -> None:
    # Points the warning at the code that called the public function.
    warnings.warn(message, KlintWarning, stacklevel=3)


def _reason(error: Exception) -> str:
    """Return why ``error`` happened, in the words a user reads."""
    if isinstance(error, OSError) and error.strerror:
        return error.strerror
    return str(error) or type(error).__name__
