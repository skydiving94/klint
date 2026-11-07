from dataclasses import dataclass
from typing import ClassVar

from klint.catalog.change_summary.documents import ChangeKind, HunkSummary
from klint.catalog.change_summary.units.summary_context import (
    ChangeSummaryContext,
    SummaryLevel,
)
from klint.core.models.units import AuditableUnit, Location


@dataclass(frozen=True)
class AuditableHunkSummaryUnit(AuditableUnit):
    """The summary of one hunk: a claim, whose evidence is the hunk's code.

    The hunk holds its summary, None when it was left out. file_path,
    file_old_path and file_change_kind describe the file the hunk changes.
    """

    unit_type: ClassVar[str] = "hunk_summary"

    hunk: HunkSummary
    file_path: str
    file_old_path: str | None = None
    file_change_kind: ChangeKind = ChangeKind.MODIFIED

    def get_location(self) -> Location | None:
        """Return where the summary sits in the document; None if it is left out."""
        return locate_summary(self.hunk.pointer)

    def get_evidence_location(self) -> Location:
        """Return the lines the hunk adds, in the file after the change.

        For a hunk that only removes lines, return the lines it removes, in
        the file before the change.
        """
        header = self.hunk.header
        if header.new_line_count > 0:
            return Location(
                path=self.file_path,
                start_line=header.new_start,
                end_line=header.new_start + header.new_line_count - 1,
            )
        return Location(
            path=self.file_old_path or self.file_path,
            start_line=header.old_start,
            end_line=header.old_start + header.old_line_count - 1,
        )

    def get_context(self) -> ChangeSummaryContext:
        return ChangeSummaryContext(
            level=SummaryLevel.HUNK, path=self.file_path, summary=self.hunk.summary
        )


def locate_summary(pointer: str | None) -> Location | None:
    """Return where a summary sits, from the pointer of what it summarizes."""
    return None if pointer is None else Location(path=f"{pointer}/summary")
