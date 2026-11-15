"""Reads a change from a git repository: its files and their hunks."""

from klint.catalog.domain_neutral.git.blob_hashes import (
    BlobHashMismatch,
    find_blob_hash_mismatches,
)
from klint.catalog.domain_neutral.git.change_scope import (
    ChangedUnitSelector,
    ChangeScope,
    DiffUnits,
    LineSpan,
    scope_audit_to_change,
)
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
from klint.catalog.domain_neutral.git.git_diff_parser import parse_git_diff

__all__ = [
    "BlobHashMismatch",
    "ChangeKind",
    "ChangeScope",
    "ChangedUnitSelector",
    "DiffUnits",
    "GitChange",
    "GitChangeSource",
    "GitChangeSourceFactory",
    "GitFileChange",
    "GitHunk",
    "HunkHeader",
    "LineSpan",
    "find_blob_hash_mismatches",
    "parse_git_diff",
    "parse_hunk_header",
    "scope_audit_to_change",
]
