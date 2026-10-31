from abc import ABC, abstractmethod
from pathlib import Path

from klint.core.models.unit_traits import UnitTraits


class BaseFileTraitsIdentifier(ABC):
    """Tells what a file is, first from the outside, then from its start."""

    @abstractmethod
    def identify(self, path: str | Path, scan_root: Path | None = None) -> UnitTraits:
        """Return what can be told about the file at ``path`` before it is read.

        scan_root is the directory the scan started from. What the path
        tells is read only from the part of it beneath scan_root, so that
        the folders above the target tell nothing; without a root, from the
        whole path as given.
        """

    def identify_from_file_start(
        self, path: Path, traits: UnitTraits, file_start: str
    ) -> UnitTraits:
        """Return the traits of ``path`` once its start, a text, has been read.

        ``traits`` are those identify gave it. By default they are kept.
        """
        del path, file_start
        return traits
