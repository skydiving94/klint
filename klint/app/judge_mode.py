"""Where the judge runs."""

from enum import StrEnum


class JudgeMode(StrEnum):
    """Where the model that answers the rule questions runs.

    LOCAL loads it in this process; REMOTE asks a server over HTTP. The
    values are what the KEV_MODE setting accepts.
    """

    LOCAL = "local"
    REMOTE = "remote"
