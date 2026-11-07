"""A change and an agent's summaries of it, level by level.

The code of each hunk comes from git; the summaries come from the agent. A
summary the agent did not write is None.
"""

from dataclasses import dataclass

from klint.catalog.domain_neutral.git import ChangeKind, HunkHeader

__all__ = [
    "ROOT_PACKAGE_PATH",
    "SUPPORTED_SCHEMA_VERSION",
    "ChangeKind",
    "ChangeSummaryDocument",
    "FileSummary",
    "HunkSummary",
    "PackageSummary",
    "is_path_inside_package",
]

# The one version of the document's format there is.
SUPPORTED_SCHEMA_VERSION = 1
# The path of the root package: the directory the change is in.
ROOT_PACKAGE_PATH = "."


@dataclass(frozen=True)
class HunkSummary:
    """One hunk of a file's diff, as ``git diff -U0`` gives it, and its summary.

    header says which lines the hunk removes and adds. removed_lines and
    added_lines are those lines, without the leading "-" or "+". pointer is
    where the hunk sits in the document, and None when the document leaves
    it out.
    """

    hunk_id: str
    header: HunkHeader
    removed_lines: tuple[str, ...]
    added_lines: tuple[str, ...]
    summary: str | None
    pointer: str | None


@dataclass(frozen=True)
class FileSummary:
    """One changed file, the summaries of its hunks, and its own summary.

    old_path is the path before the change, for a renamed file only.
    pointer is where the file sits in the document, and None when the
    document leaves it out.
    """

    path: str
    old_path: str | None
    change_kind: ChangeKind
    summary: str | None
    hunks: tuple[HunkSummary, ...]
    pointer: str | None


@dataclass(frozen=True)
class PackageSummary:
    """A directory of the change, what is summarized inside it, and its summary.

    packages and files are the packages and files directly inside it.
    pointer is where the package sits in the document.
    """

    path: str
    summary: str | None
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


def is_path_inside_package(path: str, package_path: str) -> bool:
    """Return True when ``path`` is below the directory ``package_path``."""
    if package_path == ROOT_PACKAGE_PATH:
        return path != ROOT_PACKAGE_PATH and not path.startswith(("/", "../"))
    return path.startswith(f"{package_path}/")
