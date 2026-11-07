"""A change-summary document, in either form, and how klint reads it.

A document holds each hunk's code beside its summary, or holds summaries
only and names a change that klint reads from git.
"""

from klint.catalog.change_summary.documents.change_summary_source import (
    ChangeSummaryInput,
    ChangeSummarySourceFactory,
)
from klint.catalog.change_summary.documents.document import (
    ROOT_PACKAGE_PATH,
    ChangeKind,
    ChangeSummaryDocument,
    FileSummary,
    HunkSummary,
    PackageSummary,
)
from klint.catalog.change_summary.documents.document_reader import (
    read_change_summary_document,
)
from klint.catalog.change_summary.documents.git_summaries_reader import (
    read_summaries_of_git_change,
)

__all__ = [
    "ROOT_PACKAGE_PATH",
    "ChangeKind",
    "ChangeSummaryDocument",
    "ChangeSummaryInput",
    "ChangeSummarySourceFactory",
    "FileSummary",
    "HunkSummary",
    "PackageSummary",
    "read_change_summary_document",
    "read_summaries_of_git_change",
]
