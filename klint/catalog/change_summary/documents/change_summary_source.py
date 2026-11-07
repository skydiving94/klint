"""Reads a change-summary document, and the change from git when it names one."""

import dataclasses
from dataclasses import dataclass
from pathlib import Path

from klint.catalog.change_summary.documents.git_summaries_reader import (
    read_git_change_selection,
)
from klint.catalog.domain_neutral import JsonDocumentSourceFactory
from klint.catalog.domain_neutral.git import GitChange, GitChangeSourceFactory
from klint.core.interfaces import (
    BaseAuditSource,
    BaseAuditSourceFactory,
    BaseScanProgressListener,
)
from klint.core.models.audits import AuditInput, DiskPathInput
from klint.core.models.reports import JsonValue


@dataclass(frozen=True)
class ChangeSummaryInput:
    """A parsed change-summary document, and the change it names, read from git.

    git_change is None for a document that holds the code of each hunk.
    """

    document: JsonValue
    git_change: GitChange | None = None


class ChangeSummarySource(BaseAuditSource[ChangeSummaryInput]):
    """Reads the document, then the change it names from the current repository.

    The repository is the one the current directory is in. The document
    itself is never part of the change it summarizes, so a document inside
    the repository is left out of the change.
    """

    def __init__(self, audit_input: AuditInput) -> None:
        self._audit_input = audit_input
        self._json_source = JsonDocumentSourceFactory().create_source(audit_input)
        self._scanned_file_count = 0

    async def read_input(self) -> ChangeSummaryInput:
        """Return the document and the change it names.

        Raises OSError when the document cannot be read, and ValueError when
        it is not JSON, or the change it names cannot be read from git.
        """
        document = await self._json_source.read_input()
        self._scanned_file_count = self._json_source.count_scanned_files()
        selection = read_git_change_selection(document)
        if selection is None:
            return ChangeSummaryInput(document)
        git_source = GitChangeSourceFactory(selection.commit).create_source(
            DiskPathInput(Path.cwd())
        )
        git_change = self._leave_out_document(await git_source.read_input())
        self._scanned_file_count += len(git_change.files)
        return ChangeSummaryInput(document, git_change)

    def count_scanned_files(self) -> int:
        """Return the number of files read: the document's, and the changed files."""
        return self._scanned_file_count

    def _leave_out_document(self, git_change: GitChange) -> GitChange:
        """Return ``git_change`` without the document's own file, if it holds it."""
        if not isinstance(self._audit_input, DiskPathInput):
            return git_change
        document_path = self._audit_input.path.resolve()
        repository_path = git_change.repository_path.resolve()
        if not document_path.is_relative_to(repository_path):
            return git_change
        relative_path = document_path.relative_to(repository_path).as_posix()
        return dataclasses.replace(
            git_change,
            files=tuple(
                file
                for file in git_change.files
                if relative_path not in (file.path, file.old_path)
            ),
        )


class ChangeSummarySourceFactory(BaseAuditSourceFactory[ChangeSummaryInput]):
    """Makes the source of a change-summary document, from a file or from memory."""

    def create_source(
        self,
        audit_input: AuditInput,
        scan_progress_listener: BaseScanProgressListener | None = None,
    ) -> ChangeSummarySource:
        """Return the source of ``audit_input``; no directory is scanned.

        Raises ValueError when content in memory has a media type other than
        JSON's.
        """
        del scan_progress_listener
        return ChangeSummarySource(audit_input)
