from collections.abc import Sequence
from dataclasses import dataclass
from typing import ClassVar

from klint.catalog.change_summary.documents import ChangeKind
from klint.catalog.change_summary.units.hunk_summary_unit import (
    AuditableHunkSummaryUnit,
    locate_summary,
)
from klint.catalog.change_summary.units.summary_context import (
    ChangeSummaryContext,
    SummaryLevel,
)
from klint.core.models.units import AuditableUnit, Location


@dataclass(frozen=True)
class AuditableFileSummaryUnit(AuditableUnit):
    """The summary of one changed file, judged against its hunks' summaries.

    summary is None when it was left out. old_path is the path before the
    change, for a renamed file only. pointer is where the file sits in the
    change-summary document, None when the document leaves it out.
    """

    unit_type: ClassVar[str] = "file_summary"

    path: str
    summary: str | None
    pointer: str | None
    change_kind: ChangeKind = ChangeKind.MODIFIED
    old_path: str | None = None
    hunks: tuple[AuditableHunkSummaryUnit, ...] = ()

    def get_location(self) -> Location | None:
        """Return where the summary sits in the document; None if it is left out."""
        return locate_summary(self.pointer)

    def get_context(self) -> ChangeSummaryContext:
        return ChangeSummaryContext(
            level=SummaryLevel.FILE, path=self.path, summary=self.summary
        )

    def list_children(self) -> Sequence[AuditableUnit]:
        return self.hunks
