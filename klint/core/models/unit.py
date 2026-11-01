from __future__ import annotations

from abc import ABC
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import ClassVar

from klint.core.models.location import Location
from klint.core.models.unit_traits import UnitTraits


@dataclass(frozen=True)
class UnitContext:
    """What a finding tells about its unit beyond its ID and location.

    A unit type with more to tell extends it with fields of its own.
    """


@dataclass(frozen=True)
class AuditableUnit(ABC):
    """Abstract base node for any auditable unit.

    unit_type is a per-class string tag (not a per-instance field). Each
    concrete subclass declares its own constant; it is the tag JSON rules
    use in unit_types. A unit class becomes known to an audit when
    its suite adds it to the UnitRegistry.

    traits are what is known about the unit from the outside, such as the
    language its content is written in; rules can be limited by them. A
    unit holds data only: what the judge reads about it is written by the
    renderer its kind of audit gives its class.
    """

    unit_id: str
    traits: UnitTraits = field(default_factory=UnitTraits, kw_only=True)

    unit_type: ClassVar[str]

    @property
    def language(self) -> str | None:
        """Return the language of this unit's content; None when it has none."""
        return self.traits.language

    def get_location(self) -> Location | None:
        """Return where this unit sits in its source, if it has a location."""
        return None

    def get_context(self) -> UnitContext:
        """Return what a finding on this unit tells beyond its ID and location."""
        return UnitContext()

    def get_evidence_location(self) -> Location | None:
        """Return where this unit's evidence sits, when apart from the unit itself."""
        return None

    def list_children(self) -> Sequence[AuditableUnit]:
        """Return the units nested directly inside this one."""
        return ()
