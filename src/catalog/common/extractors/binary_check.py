"""Tells a binary file from a text file without reading all of it."""

from pathlib import Path

_BYTES_TO_CHECK = 1024


def is_likely_binary(path: Path) -> bool:
    """Return True when the start of the file holds a NUL byte or cannot be read."""
    try:
        with path.open("rb") as file:
            chunk = file.read(_BYTES_TO_CHECK)
        return b"\x00" in chunk
    except OSError:
        return True
