"""Units and extractors for Python code."""

from src.catalog.code.python.units.package import AuditablePythonPackageUnit
from src.core.registry import UnitRegistry


def register(registry: UnitRegistry) -> None:
    """Add this suite's unit types to ``registry``."""
    registry.register_unit(AuditablePythonPackageUnit)
