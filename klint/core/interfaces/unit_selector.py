"""Chooses, among the units an input holds, the ones an audit goes on with."""

from abc import ABC, abstractmethod
from collections.abc import Sequence

from klint.core.models.units import AuditableUnit


class BaseUnitSelector(ABC):
    """Keeps some of the units extracted from an audit input, before any rule applies.

    A selector lets a run audit part of what its input holds, such as the
    units a change touches. What it leaves out is neither asked about nor
    reported.
    """

    @abstractmethod
    def select_units(self, units: Sequence[AuditableUnit]) -> list[AuditableUnit]:
        """Return the units of ``units`` to audit, in their order: all, some or none."""
