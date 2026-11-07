"""What a finding on a summary tells beyond the unit's ID and location."""

from dataclasses import dataclass
from enum import StrEnum

from klint.core.models.unit import UnitContext


class SummaryLevel(StrEnum):
    """The level of a change a summary is about.

    The summary of the root package is the summary of the whole commit.
    """

    HUNK = "hunk"
    FILE = "file"
    PACKAGE = "package"
    COMMIT = "commit"


@dataclass(frozen=True)
class ChangeSummaryContext(UnitContext):
    """The level a summary is at, the path it is about, and the summary itself.

    path is the path of the hunk's file, of the file, or of the package.
    """

    level: SummaryLevel = SummaryLevel.HUNK
    path: str = ""
    summary: str = ""
