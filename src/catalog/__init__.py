"""Built-in suites of auditable units and their extractors.

A unit type becomes known to rule validation when its class is defined, so
this package imports every built-in unit module. Importing anything from the
catalog therefore registers all of them.
"""

from src.catalog.code.common.units.directory import AuditableProjectDirectoryUnit
from src.catalog.code.common.units.file_metadata import AuditableFileMetadataUnit
from src.catalog.common.units.file import AuditableFileUnit

__all__ = [
    "AuditableFileMetadataUnit",
    "AuditableFileUnit",
    "AuditableProjectDirectoryUnit",
]
