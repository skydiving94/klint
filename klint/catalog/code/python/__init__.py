"""Units and extractors for Python code."""

from klint.catalog.code.python.definition_renderers import (
    PythonClassRenderer,
    PythonFunctionRenderer,
)
from klint.catalog.code.python.definition_units import (
    AuditablePythonClassUnit,
    AuditablePythonDefinitionUnit,
    AuditablePythonFunctionUnit,
    PythonDefinitionContext,
)
from klint.catalog.code.python.file_metadata_extractor import (
    PythonFileMetadataExtractor,
)
from klint.catalog.code.python.package_factory import PythonPackageUnitFactory
from klint.catalog.code.python.package_renderer import PythonPackageRenderer
from klint.catalog.code.python.package_unit import AuditablePythonPackageUnit
from klint.catalog.code.python.source_file_extractor import PythonSourceFileExtractor
from klint.catalog.code.python.source_file_unit import AuditablePythonFileUnit

# The language this suite handles, under the name the language data gives it.
SUITE_LANGUAGE = "python"

__all__ = [
    "SUITE_LANGUAGE",
    "AuditablePythonClassUnit",
    "AuditablePythonDefinitionUnit",
    "AuditablePythonFileUnit",
    "AuditablePythonFunctionUnit",
    "AuditablePythonPackageUnit",
    "PythonClassRenderer",
    "PythonDefinitionContext",
    "PythonFileMetadataExtractor",
    "PythonFunctionRenderer",
    "PythonPackageRenderer",
    "PythonPackageUnitFactory",
    "PythonSourceFileExtractor",
]
