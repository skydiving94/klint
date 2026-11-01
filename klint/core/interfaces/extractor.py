from abc import ABC, abstractmethod
from typing import Generic, TypeVar

from klint.core.models.unit import AuditableUnit

# What an extractor reads units from: a scanned file, a scanned target or a
# parsed document, for example.
InputT_contra = TypeVar("InputT_contra", contravariant=True)


class BaseUnitExtractor(ABC, Generic[InputT_contra]):
    """Turns one input into the units to audit."""

    @abstractmethod
    async def extract(self, audit_input: InputT_contra) -> list[AuditableUnit]:
        """Return the units extracted from ``audit_input``; there may be none.

        When the input holds nested units, a unit comes before the units
        nested inside it. Raises ValueError when this extractor cannot take
        such an input.
        """
