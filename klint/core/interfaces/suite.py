from abc import ABC, abstractmethod

from klint.core.models.audit_kind import AuditKind
from klint.core.registry import UnitRegistry


class BaseSuite(ABC):
    """A set of unit types and the kinds of audit built on them."""

    @abstractmethod
    def list_audit_kinds(self) -> list[AuditKind]:
        """Return the kinds of audit this suite offers; there may be none."""

    @abstractmethod
    def register_unit_types(self, registry: UnitRegistry) -> None:
        """Add the unit types this suite's units declare to ``registry``."""
