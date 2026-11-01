"""A file as the delegator hands it to the extractor its traits pick."""

from dataclasses import dataclass
from pathlib import Path

from klint.core.models.unit_traits import UnitTraits


@dataclass(frozen=True)
class DispatchedFile:
    """A scanned file, with what was checked before it is extracted.

    traits are those the scan identified for it. is_binary is True when its
    content is not text, so that an extractor does not read it as text.
    """

    path: Path
    traits: UnitTraits
    is_binary: bool
