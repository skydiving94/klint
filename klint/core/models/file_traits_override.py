"""What a project says about some of its files, over what klint detects."""

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class FileTraitsOverride:
    """The traits a project gives the files that a glob matches.

    glob is matched against a file's path from base_directory down, such as
    "src/api/**". language, when set, replaces the detected language, and
    tags, when set, replace every detected tag. Both are in lower case.
    """

    base_directory: Path
    glob: str
    language: str | None = None
    tags: frozenset[str] | None = None
