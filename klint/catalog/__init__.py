"""Built-in suites of auditable units and their extractors."""

from klint.catalog import common
from klint.catalog.code import common as code_common
from klint.core.registry import UnitRegistry


def register(registry: UnitRegistry) -> None:
    """Add the unit types of every built-in suite to ``registry``."""
    common.register(registry)
    code_common.register(registry)
