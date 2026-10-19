"""What the exit status of a klint command tells the shell."""

from enum import IntEnum


class ExitCode(IntEnum):
    """The exit status of a command.

    PROBLEMS_FOUND means at least one failure was found with the confidence
    the command line asks for. RUN_ERROR means the audit could not run, for
    example because the target or a rules file cannot be used.
    """

    NO_PROBLEMS = 0
    PROBLEMS_FOUND = 1
    RUN_ERROR = 2
