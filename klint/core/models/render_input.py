"""What a renderer is given to write the text the judge reads about a unit."""

from dataclasses import dataclass

from klint.core.models.report import AuditFinding
from klint.core.models.unit import AuditableUnit


@dataclass(frozen=True)
class RenderInput:
    """One unit to describe to the judge, and what is known about it so far.

    unit is the unit judged. child_findings are the findings on the units
    nested directly inside it that were judged before it, in the order of
    its children, each child's findings in rule order. They are empty unless
    the audit judges children before their parents.
    """

    unit: AuditableUnit
    child_findings: tuple[AuditFinding, ...] = ()
