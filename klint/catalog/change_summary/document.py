"""A change-summary document: an agent's summaries of one change, level by level.

The code of each hunk comes from git; the summaries come from the agent.
"""

from dataclasses import dataclass
from enum import StrEnum

# The one version of the document's format there is.
SUPPORTED_SCHEMA_VERSION = 1


class ChangeKind(StrEnum):
    """What a change does to a file."""

    ADDED = "added"
    MODIFIED = "modified"
    DELETED = "deleted"
    RENAMED = "renamed"


@dataclass(frozen=True)
class HunkSummary:
    """One hunk of a file's diff, as ``git diff -U0`` gives it, and its summary.

    The hunk removes old_line_count lines from old_start in the file before
    the change, and adds new_line_count lines from new_start in the file
    after it. removed_lines and added_lines are those lines, without the
    leading "-" or "+". pointer is where the hunk sits in the document.
    """

    hunk_id: str
    old_start: int
    old_line_count: int
    new_start: int
    new_line_count: int
    removed_lines: tuple[str, ...]
    added_lines: tuple[str, ...]
    summary: str
    pointer: str


@dataclass(frozen=True)
class FileSummary:
    """One changed file, the summaries of its hunks, and its own summary.

    old_path is the path before the change, for a renamed file only.
    pointer is where the file sits in the document.
    """

    path: str
    old_path: str | None
    change_kind: ChangeKind
    summary: str
    hunks: tuple[HunkSummary, ...]
    pointer: str


@dataclass(frozen=True)
class PackageSummary:
    """A directory of the change, what is summarized inside it, and its summary.

    packages and files are the packages and files directly inside it.
    pointer is where the package sits in the document.
    """

    path: str
    summary: str
    packages: tuple["PackageSummary", ...]
    files: tuple[FileSummary, ...]
    pointer: str


@dataclass(frozen=True)
class ChangeSummaryDocument:
    """The summaries of one change, from its hunks up to the whole commit.

    diff_command is the command whose output the hunks come from. The
    summary of root_package, the directory "." the change is in, is the
    summary of the commit.
    """

    schema_version: int
    diff_command: str
    root_package: PackageSummary
