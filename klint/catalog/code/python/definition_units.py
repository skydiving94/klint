"""The classes and functions of a Python file, each a unit of its own."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import ClassVar

from klint.core.models.units import AuditableUnit, Location, UnitContext


@dataclass(frozen=True)
class PythonDefinitionContext(UnitContext):
    """The name a class or function is reached by from the top of its file.

    qualified_name joins the names of the classes it is defined in and its
    own with dots, as in "Order.total".
    """

    qualified_name: str = ""


@dataclass(frozen=True)
class AuditablePythonDefinitionUnit(AuditableUnit):
    """A class or function defined in a Python file.

    source is its text as the file writes it, decorators included, from
    start_line to end_line. qualified_name is the name it is reached by from
    the top of its file.
    """

    qualified_name: str = ""
    file_path: str = ""
    start_line: int = 1
    end_line: int = 1
    source: str = ""

    def get_location(self) -> Location:
        return Location(
            path=self.file_path, start_line=self.start_line, end_line=self.end_line
        )

    def get_context(self) -> PythonDefinitionContext:
        return PythonDefinitionContext(qualified_name=self.qualified_name)


@dataclass(frozen=True)
class AuditablePythonFunctionUnit(AuditablePythonDefinitionUnit):
    """A function or method, async or not, with any function defined inside it.

    body_start_line is the first line of its body after its docstring, when
    that line holds nothing of the signature; None when there is no such
    line, as for a function whose body is its docstring alone.
    """

    unit_type: ClassVar[str] = "function"

    body_start_line: int | None = None


@dataclass(frozen=True)
class AuditablePythonClassUnit(AuditablePythonDefinitionUnit):
    """A class, holding the methods and classes defined in its body."""

    unit_type: ClassVar[str] = "class"

    members: tuple[AuditablePythonDefinitionUnit, ...] = ()

    def list_children(self) -> Sequence[AuditableUnit]:
        return self.members
