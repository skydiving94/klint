"""The warning klint raises when it carries on after ignoring something."""

import warnings
from pathlib import Path


class KlintWarning(UserWarning):
    """Something was ignored or left out; the run continues."""


def warn_about_unreadable_file(path: Path, error: OSError) -> None:
    """Warn that the file at ``path`` is left out because it cannot be read."""
    reason = error.strerror or str(error)
    warnings.warn(
        f"File '{path}' is left out: it cannot be read ({reason})",
        KlintWarning,
        stacklevel=2,
    )
