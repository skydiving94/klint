"""What klint-change-summary prints to help an agent write summaries."""

from dataclasses import dataclass
from enum import Enum

from klint.cli.audit_command import KlintCommand
from klint.cli.change_summary_writing.summary_instructions import (
    InstructionsAudience,
    load_summary_instructions,
)
from klint.cli.change_summary_writing.summary_skeleton import build_summary_skeleton
from klint.cli.console import print_error_line
from klint.cli.exit_code import ExitCode


class WritingAidKind(Enum):
    """What the command prints: the writing instructions, or the change's skeleton."""

    INSTRUCTIONS = "instructions"
    SKELETON = "skeleton"


@dataclass(frozen=True)
class WritingAid:
    """One aid to print.

    commit names the skeleton's commit; None for the uncommitted change.
    """

    kind: WritingAidKind
    commit: str | None = None


async def print_writing_aid(command: KlintCommand, aid: WritingAid) -> ExitCode:
    """Print ``aid`` on stdout; the judge is not asked. Return the exit code."""
    match aid.kind:
        case WritingAidKind.INSTRUCTIONS:
            print(load_summary_instructions(InstructionsAudience.ANY_AGENT))
        case WritingAidKind.SKELETON:
            try:
                skeleton = await build_summary_skeleton(aid.commit)
            except ValueError as error:
                print_error_line(command, error)
                return ExitCode.RUN_ERROR
            print(skeleton)
    return ExitCode.NO_PROBLEMS
