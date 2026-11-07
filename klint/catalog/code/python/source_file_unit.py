from collections.abc import Sequence
from dataclasses import dataclass

from klint.catalog.code.python.definition_units import (
    AuditablePythonDefinitionUnit,
)
from klint.catalog.domain_neutral import AuditableFileUnit
from klint.core.models.units import AuditableUnit


@dataclass(frozen=True)
class AuditablePythonFileUnit(AuditableFileUnit):
    """A whole Python file, holding the classes and functions defined at its top.

    members are empty when the file cannot be parsed.
    """

    members: tuple[AuditablePythonDefinitionUnit, ...] = ()

    def list_children(self) -> Sequence[AuditableUnit]:
        return self.members
