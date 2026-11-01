from dataclasses import dataclass
from typing import ClassVar

from klint.catalog.change_summary.document import ChangeKind, HunkSummary
from klint.catalog.change_summary.units.summary_context import (
    ChangeSummaryContext,
    SummaryLevel,
)
from klint.core.models.location import Location
from klint.core.models.unit import AuditableUnit


@dataclass(frozen=True)
class AuditableHunkSummaryUnit(AuditableUnit):
    """The summary of one hunk: a claim, whose evidence is the hunk's code.

    file_path, file_old_path and file_change_kind describe the file the hunk
    changes.
    """

    unit_type: ClassVar[str] = "hunk_summary"

    hunk: HunkSummary
    file_path: str
    file_old_path: str | None = None
    file_change_kind: ChangeKind = ChangeKind.MODIFIED

    def get_location(self) -> Location:
        """Return where the summary sits in the change-summary document."""
        return Location(path=f"{self.hunk.pointer}/summary")

    def get_evidence_location(self) -> Location:
        """Return the lines the hunk adds, in the file after the change.

        For a hunk that only removes lines, return the lines it removes, in
        the file before the change.
        """
        hunk = self.hunk
        if hunk.new_line_count > 0:
            return Location(
                path=self.file_path,
                start_line=hunk.new_start,
                end_line=hunk.new_start + hunk.new_line_count - 1,
            )
        return Location(
            path=self.file_old_path or self.file_path,
            start_line=hunk.old_start,
            end_line=hunk.old_start + hunk.old_line_count - 1,
        )

    def get_context(self) -> ChangeSummaryContext:
        return ChangeSummaryContext(
            level=SummaryLevel.HUNK, path=self.file_path, summary=self.hunk.summary
        )
