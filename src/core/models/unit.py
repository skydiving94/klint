from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, ClassVar, Dict, Optional

from src.core.models.location import Location


@dataclass(frozen=True)
class AuditableUnit(ABC):
    """Abstract base node for any auditable unit.

    unit_type is a per-class string tag (not a per-instance field). Each
    concrete subclass declares its own constant; it is the tag JSON rules
    use in target_unit_types. A unit class becomes known to an audit when
    its suite adds it to the UnitRegistry.

    language is the language this unit's content is written in, programming
    or natural (for example "python" or "english"). It is None when unknown
    or when the content has no language, such as an image.
    """

    unit_id: str
    language: Optional[str] = field(default=None, kw_only=True)

    unit_type: ClassVar[str]

    @abstractmethod
    def get_content(self) -> str:
        """Return the string representation of this unit (and any child units) for evaluation."""
        pass

    @abstractmethod
    def get_metadata(self) -> Dict[str, Any]:
        """Return unit-specific context metadata to attach to an AuditFinding."""
        pass

    def get_location(self) -> Optional[Location]:
        """Return where this unit sits in its source, if it has a location."""
        return None
