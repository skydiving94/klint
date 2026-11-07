"""Reads a change from a git repository: its files and their hunks."""

from klint.catalog.domain_neutral.git.git_change import (
    ChangeKind,
    GitChange,
    GitFileChange,
    GitHunk,
    HunkHeader,
    parse_hunk_header,
)
from klint.catalog.domain_neutral.git.git_change_source import (
    GitChangeSource,
    GitChangeSourceFactory,
)

__all__ = [
    "ChangeKind",
    "GitChange",
    "GitChangeSource",
    "GitChangeSourceFactory",
    "GitFileChange",
    "GitHunk",
    "HunkHeader",
    "parse_hunk_header",
]
