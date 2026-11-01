from collections.abc import Sequence
from dataclasses import dataclass
from typing import ClassVar

from klint.catalog.change_summary.units.file_summary import AuditableFileSummaryUnit
from klint.catalog.change_summary.units.summary_context import (
    ChangeSummaryContext,
    SummaryLevel,
)
from klint.core.models.location import Location
from klint.core.models.unit import AuditableUnit


@dataclass(frozen=True)
class AuditablePackageSummaryUnit(AuditableUnit):
    """The summary of a directory of the change, judged against those inside it.

    The root package, the directory the change is in, has the summary of
    the whole commit. pointer is where the package sits in the
    change-summary document.
    """

    unit_type: ClassVar[str] = "package_summary"

    path: str
    summary: str
    pointer: str
    is_root_package: bool = False
    packages: tuple["AuditablePackageSummaryUnit", ...] = ()
    files: tuple[AuditableFileSummaryUnit, ...] = ()

    @property
    def level(self) -> SummaryLevel:
        """Return COMMIT for the root package, PACKAGE for any other."""
        return SummaryLevel.COMMIT if self.is_root_package else SummaryLevel.PACKAGE

    def get_location(self) -> Location:
        """Return where the summary sits in the change-summary document."""
        return Location(path=f"{self.pointer}/summary")

    def get_context(self) -> ChangeSummaryContext:
        return ChangeSummaryContext(
            level=self.level, path=self.path, summary=self.summary
        )

    def children(self) -> Sequence[AuditableUnit]:
        return [*self.packages, *self.files]
