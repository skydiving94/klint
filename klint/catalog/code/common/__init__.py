"""Units and extractors shared by every programming language."""

from klint.catalog.code.common.units.directory import AuditableDirectoryUnit
from klint.catalog.code.common.units.file_metadata import AuditableFileMetadataUnit
from klint.core.registry import UnitRegistry


def register(registry: UnitRegistry) -> None:
    """Add this suite's unit types to ``registry``."""
    registry.register_unit(AuditableFileMetadataUnit)
    registry.register_unit(AuditableDirectoryUnit)
