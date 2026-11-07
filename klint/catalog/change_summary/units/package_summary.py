from collections.abc import Sequence
from dataclasses import dataclass
from typing import ClassVar

from klint.catalog.change_summary.units.file_summary import AuditableFileSummaryUnit
from klint.catalog.change_summary.units.hunk_summary_unit import locate_summary
from klint.catalog.change_summary.units.summary_context import (
    ChangeSummaryContext,
    SummaryLevel,
)
from klint.core.models.units import AuditableUnit, Location


@dataclass(frozen=True)
class AuditablePackageSummaryUnit(AuditableUnit):
    """The summary of a directory of the change, judged against those inside it.

    The root package, the directory the change is in, has the summary of
    the whole commit; summary is None when it was left out. pointer is where
    the package sits in the change-summary document.
    """

    unit_type: ClassVar[str] = "package_summary"

    path: str
    summary: str | None
    pointer: str
    is_root_package: bool = False
    packages: tuple["AuditablePackageSummaryUnit", ...] = ()
    files: tuple[AuditableFileSummaryUnit, ...] = ()

    @property
    def level(self) -> SummaryLevel:
        """Return COMMIT for the root package, PACKAGE for any other."""
        return SummaryLevel.COMMIT if self.is_root_package else SummaryLevel.PACKAGE

    def get_location(self) -> Location | None:
        """Return where the summary sits in the document; None if it is left out."""
        return locate_summary(self.pointer)

    def get_context(self) -> ChangeSummaryContext:
        return ChangeSummaryContext(
            level=self.level, path=self.path, summary=self.summary
        )

    def list_children(self) -> Sequence[AuditableUnit]:
        return [*self.packages, *self.files]
