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


def warn_about_unparseable_file(path: Path, error: Exception) -> None:
    """Warn that the file at ``path`` is described by its name and line count only.

    The parser gave up on it, so what it declares and imports is unknown.
    """
    _warn(
        f"File '{path}' is listed by name and line count only: "
        f"it cannot be parsed ({_reason(error)})"
    )


def describe_deprecated_name(old_name: str, new_name: str, place: str = "") -> str:
    """Return the message saying ``old_name`` still works, for now, as ``new_name``.

    ``place`` says where the old name was found, such as "in 'klint.json'".
    """
    found_at = f" {place}" if place else ""
    return (
        f"'{old_name}'{found_at} is deprecated and stops working in the next "
        f"release; use '{new_name}' instead"
    )


def warn_about_deprecated_name(old_name: str, new_name: str, place: str = "") -> None:
    """Warn that ``old_name`` was used; it still works, for now, as ``new_name``."""
    _warn(describe_deprecated_name(old_name, new_name, place))


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
    if isinstance(error, SyntaxError) and error.msg:
        # Leaves out the file name, which the warning gives in full.
        return f"{error.msg}, line {error.lineno}" if error.lineno else error.msg
    return str(error) or type(error).__name__
