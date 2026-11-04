"""Builds the summaries of a git change into a tree of packages, files and hunks.

Each listed package, and each file of the change, is placed inside the
deepest listed package that holds it, else inside the root package.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from klint.catalog.change_summary.document import (
    ROOT_PACKAGE_PATH,
    FileSummary,
    HunkSummary,
    PackageSummary,
    is_path_inside_package,
)
from klint.catalog.domain_neutral.git import GitFileChange, HunkHeader


@dataclass(frozen=True)
class SummaryEntry:
    """A summary a document gives, and where it sits; summary is None if left out."""

    summary: str | None
    pointer: str


@dataclass(frozen=True)
class FileEntry:
    """A file a document lists: its own summary and those of its hunks."""

    own: SummaryEntry
    header_to_hunk_entry: Mapping[HunkHeader, SummaryEntry]


def build_file_summary(file: GitFileChange, entry: FileEntry | None) -> FileSummary:
    """Return ``file`` with the summaries ``entry`` gives; None for those left out."""
    header_to_hunk_entry = {} if entry is None else entry.header_to_hunk_entry
    hunks = []
    for number, hunk in enumerate(file.hunks, start=1):
        hunk_entry = header_to_hunk_entry.get(hunk.header)
        hunks.append(
            HunkSummary(
                hunk_id=f"{file.path}#{number}",
                header=hunk.header,
                removed_lines=hunk.removed_lines,
                added_lines=hunk.added_lines,
                summary=None if hunk_entry is None else hunk_entry.summary,
                pointer=None if hunk_entry is None else hunk_entry.pointer,
            )
        )
    return FileSummary(
        path=file.path,
        old_path=file.old_path,
        change_kind=file.change_kind,
        summary=None if entry is None else entry.own.summary,
        hunks=tuple(hunks),
        pointer=None if entry is None else entry.own.pointer,
    )


def build_package_summary(
    path: str,
    entry: SummaryEntry,
    path_to_package_entry: Mapping[str, SummaryEntry],
    files: Sequence[FileSummary],
) -> PackageSummary:
    """Return the package at ``path``, with what it is the deepest package of."""
    package_paths = list(path_to_package_entry)
    return PackageSummary(
        path=path,
        summary=entry.summary,
        packages=tuple(
            build_package_summary(
                package_path, package_entry, path_to_package_entry, files
            )
            for package_path, package_entry in path_to_package_entry.items()
            if _find_holder_path(package_path, package_paths) == path
        ),
        files=tuple(
            file
            for file in files
            if _find_holder_path(file.path, package_paths) == path
        ),
        pointer=entry.pointer,
    )


def _find_holder_path(path: str, package_paths: Sequence[str]) -> str:
    """Return the deepest of ``package_paths`` that holds ``path``, else the root."""
    holder_paths = [
        package_path
        for package_path in package_paths
        if is_path_inside_package(path, package_path)
    ]
    return max(holder_paths, key=len, default=ROOT_PACKAGE_PATH)
