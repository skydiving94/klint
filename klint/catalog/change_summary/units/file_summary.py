from collections.abc import Sequence
from dataclasses import dataclass
from typing import ClassVar

from klint.catalog.change_summary.document import ChangeKind
from klint.catalog.change_summary.units.hunk_summary_unit import (
    AuditableHunkSummaryUnit,
)
from klint.catalog.change_summary.units.summary_context import (
    ChangeSummaryContext,
    SummaryLevel,
)
from klint.core.models.location import Location
from klint.core.models.unit import AuditableUnit


@dataclass(frozen=True)
class AuditableFileSummaryUnit(AuditableUnit):
    """The summary of one changed file, judged against its hunks' summaries.

    old_path is the path before the change, for a renamed file only.
    pointer is where the file sits in the change-summary document.
    """

    unit_type: ClassVar[str] = "file_summary"

    path: str
    summary: str
    pointer: str
    change_kind: ChangeKind = ChangeKind.MODIFIED
    old_path: str | None = None
    hunks: tuple[AuditableHunkSummaryUnit, ...] = ()

    def get_location(self) -> Location:
        """Return where the summary sits in the change-summary document."""
        return Location(path=f"{self.pointer}/summary")

    def get_context(self) -> ChangeSummaryContext:
        return ChangeSummaryContext(
            level=SummaryLevel.FILE, path=self.path, summary=self.summary
        )

    def children(self) -> Sequence[AuditableUnit]:
        return self.hunks
