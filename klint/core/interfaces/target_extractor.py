from abc import ABC, abstractmethod

from klint.core.models.scanned_tree import ScannedTarget
from klint.core.models.unit import AuditableUnit


class BaseTargetExtractor(ABC):
    """Turns a scanned audit target into every unit an audit goes through."""

    @abstractmethod
    async def extract_units(self, scanned_target: ScannedTarget) -> list[AuditableUnit]:
        """Return the units of ``scanned_target``, nested ones included.

        A unit comes before the units nested inside it. Raises ValueError
        when this extractor cannot take such a target.
        """
