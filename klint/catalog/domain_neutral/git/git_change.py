"""A change to the files of a git repository, hunk by hunk, as git's diff gives it."""

import re
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

# A hunk header as git writes it; a side's line count is left out when it is 1.
_HUNK_HEADER_PATTERN = re.compile(r"@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")


class ChangeKind(StrEnum):
    """What a change does to a file."""

    ADDED = "added"
    MODIFIED = "modified"
    DELETED = "deleted"
    RENAMED = "renamed"


@dataclass(frozen=True)
class HunkHeader:
    """Where a hunk sits: the lines it removes and the lines it adds.

    The hunk removes old_line_count lines from old_start in the file before
    the change, and adds new_line_count lines from new_start in the file
    after it.
    """

    old_start: int
    old_line_count: int
    new_start: int
    new_line_count: int

    def format_text(self) -> str:
        """Return the header as git writes it, such as "@@ -20,0 +21 @@"."""
        old_span = _format_span(self.old_start, self.old_line_count)
        new_span = _format_span(self.new_start, self.new_line_count)
        return f"@@ -{old_span} +{new_span} @@"


def parse_hunk_header(text: str) -> HunkHeader:
    """Return the header that ``text``, a hunk header line, holds.

    What follows the closing "@@", such as the enclosing function git names,
    is ignored. Raises ValueError when ``text`` does not start with a hunk
    header.
    """
    match = _HUNK_HEADER_PATTERN.match(text.strip())
    if match is None:
        raise ValueError(
            f"'{text}' is not a hunk header such as '@@ -20,0 +21 @@', as "
            "git diff -U0 writes it"
        )
    old_start, old_line_count, new_start, new_line_count = match.groups()
    return HunkHeader(
        old_start=int(old_start),
        old_line_count=1 if old_line_count is None else int(old_line_count),
        new_start=int(new_start),
        new_line_count=1 if new_line_count is None else int(new_line_count),
    )


@dataclass(frozen=True)
class GitHunk:
    """One hunk of a file's diff with no lines of context, as ``git diff -U0`` gives it.

    removed_lines and added_lines are the lines the header names, without
    the leading "-" or "+".
    """

    header: HunkHeader
    removed_lines: tuple[str, ...]
    added_lines: tuple[str, ...]


@dataclass(frozen=True)
class GitFileChange:
    """One changed file: its path, what the change does to it, and its hunks.

    path is the path after the change, or before it for a deleted file.
    old_path is the path before a rename, and None for any other change. A
    binary file has no hunks, nor has a rename without edits or a file whose
    mode alone changed.
    """

    path: str
    change_kind: ChangeKind
    hunks: tuple[GitHunk, ...] = ()
    old_path: str | None = None
    is_binary: bool = False


@dataclass(frozen=True)
class GitChange:
    """The files one change touches, in git's order.

    repository_path is the top directory of the repository, which the files'
    paths are relative to. diff_command is the git command the hunks come from.
    """

    repository_path: Path
    diff_command: str
    files: tuple[GitFileChange, ...]


def _format_span(start: int, line_count: int) -> str:
    """Return a side of a hunk header as git writes it: "40", or "40,3"."""
    return str(start) if line_count == 1 else f"{start},{line_count}"
