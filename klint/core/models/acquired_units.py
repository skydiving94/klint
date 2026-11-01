"""The units read from one audit input."""

from dataclasses import dataclass

from klint.core.models.unit import AuditableUnit


@dataclass(frozen=True)
class AcquiredUnits:
    """The units read from one audit input.

    units are every unit extracted from the input, nested ones included,
    each before the units nested inside it. scanned_file_count is the number
    of files read to get them; none for content held in memory.
    """

    units: list[AuditableUnit]
    scanned_file_count: int
