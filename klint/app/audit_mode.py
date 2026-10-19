"""The kinds of audit a command can ask for."""

from enum import Enum, auto


class AuditMode(Enum):
    """What an audit examines."""

    FILE_CONTENTS = auto()
    PROJECT_STRUCTURE = auto()
