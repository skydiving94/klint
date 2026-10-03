"""Units and extractors that do not depend on what kind of content is audited."""

from src.catalog.common.units.file import AuditableFileUnit
from src.core.registry import UnitRegistry


def register(registry: UnitRegistry) -> None:
    """Add this suite's unit types to ``registry``."""
    registry.register_unit(AuditableFileUnit)
