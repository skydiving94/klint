"""Units and extractors shared by every programming language."""

from src.catalog.code.common.units.file_metadata import AuditableFileMetadataUnit
from src.core.registry import UnitRegistry


def register(registry: UnitRegistry) -> None:
    """Add this suite's unit types to ``registry``."""
    registry.register_unit(AuditableFileMetadataUnit)
