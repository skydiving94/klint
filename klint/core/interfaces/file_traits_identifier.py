from abc import ABC, abstractmethod
from pathlib import Path

from klint.core.models.unit_traits import UnitTraits


class BaseFileTraitsIdentifier(ABC):
    @abstractmethod
    def identify(self, path: str | Path, scan_root: Path | None = None) -> UnitTraits:
        """Return what can be told about the file at ``path`` before it is read.

        scan_root is the directory the scan started from. What the path
        tells is read only from the part of it beneath scan_root, so that
        the folders above the target tell nothing; without a root, from the
        whole path as given.
        """
