"""Reads the start of a file once: enough to tell binary from text, and more."""

from pathlib import Path

# How much of a file is read: enough to hold the imports of most files.
_FILE_START_SIZE = 4096
# How much of that start a NUL byte is looked for in.
_BYTES_TO_CHECK_FOR_BINARY = 1024


def read_file_start(path: Path) -> bytes:
    """Return the first bytes of the file at ``path``; all of a short file."""
    with path.open("rb") as file:
        return file.read(_FILE_START_SIZE)


def is_binary_start(file_start: bytes) -> bool:
    """Return True when the start of a file holds a NUL byte early on."""
    return b"\x00" in file_start[:_BYTES_TO_CHECK_FOR_BINARY]
