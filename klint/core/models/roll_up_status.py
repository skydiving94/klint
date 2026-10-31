"""What the problems found on a unit and on the units nested in it say about it."""

from enum import Enum


class RollUpStatus(Enum):
    """Where an audited unit's problems are: on it, beneath it, or nowhere.

    OWN_PROBLEM wins over DESCENDANT_PROBLEM: a unit with a problem of its
    own has that status whatever the units nested in it have.
    """

    NO_PROBLEM = "no_problem"
    OWN_PROBLEM = "own_problem"
    DESCENDANT_PROBLEM = "descendant_problem"
