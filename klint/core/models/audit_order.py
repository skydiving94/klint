"""The order in which an audit judges its units."""

from enum import Enum


class AuditOrder(Enum):
    """The order in which the units of an audit are judged.

    ALL_AT_ONCE judges every unit as soon as it can. CHILDREN_FIRST judges
    the deepest units first, and a unit only after every unit nested inside
    it.
    """

    ALL_AT_ONCE = "all_at_once"
    CHILDREN_FIRST = "children_first"
