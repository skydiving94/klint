"""What klint can tell about a file before reading it."""

from dataclasses import dataclass


@dataclass(frozen=True)
class FileTraits:
    """What is known about a file from the outside, before it is extracted.

    language is the language the file is written in, or None when it could
    not be told.
    """

    language: str | None = None
