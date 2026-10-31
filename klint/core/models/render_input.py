"""What a renderer is given to write the text the judge reads about a unit."""

from dataclasses import dataclass
from typing import TypeVar

from klint.core.models.report import AuditFinding
from klint.core.models.unit import AuditableUnit

# The class of unit a renderer describes.
UnitT = TypeVar("UnitT", bound=AuditableUnit)

# The most characters the judge reads about a unit, unless a kind of audit
# says otherwise: a small judge does best with short texts.
DEFAULT_CHARACTER_BUDGET = 2_000


@dataclass(frozen=True)
class RenderInput:
    """One unit to describe to the judge, and what is known about it so far.

    unit is the unit judged. The text written about it holds at most
    character_budget characters. child_findings are the findings on the
    units nested directly inside it that were judged before it, in the order
    of its children, each child's findings in rule order. They are empty
    unless the audit judges children before their parents.
    """

    unit: AuditableUnit
    character_budget: int = DEFAULT_CHARACTER_BUDGET
    child_findings: tuple[AuditFinding, ...] = ()

    def get_unit_as(self, unit_class: type[UnitT]) -> UnitT:
        """Return the unit, as a ``unit_class``.

        Raises TypeError when the unit is not a ``unit_class``.
        """
        if not isinstance(self.unit, unit_class):
            raise TypeError(
                f"Expected a {unit_class.__name__} unit, got "
                f"{type(self.unit).__name__} '{self.unit.unit_id}'"
            )
        return self.unit
