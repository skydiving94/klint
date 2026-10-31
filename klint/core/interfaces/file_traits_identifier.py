from abc import ABC, abstractmethod
from pathlib import Path

from klint.core.models.unit_traits import UnitTraits


class BaseFileTraitsIdentifier(ABC):
    @abstractmethod
    def identify(self, path: str | Path) -> UnitTraits:
        """Return what can be told about the file at ``path`` before it is read."""
        pass
