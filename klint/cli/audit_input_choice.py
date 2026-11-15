"""What a klint command audits: a path, or the staged change."""

import sys
from dataclasses import dataclass
from pathlib import Path

from klint.app.staged_change import StagedChangeScope, read_staged_change_scope
from klint.catalog.domain_neutral.git import DiffUnits
from klint.cli.audit_command import AuditCommand
from klint.cli.command_arguments import CommandArguments
from klint.cli.console import print_warning_line
from klint.core.interfaces import BaseUnitSelector
from klint.core.models.audits import AuditInput, DiskPathInput


@dataclass(frozen=True)
class ChosenAuditInput:
    """What one run audits, and where its acknowledgement log is looked for.

    staged is the staged change, when the run audits it; None for a path.
    """

    audit_input: AuditInput
    log_directory: Path
    staged: StagedChangeScope | None = None

    def find_unit_selector(self) -> BaseUnitSelector | None:
        """Return what keeps the units of the change; None for a path."""
        return None if self.staged is None else self.staged.scope.unit_selector


async def choose_audit_input(
    command: AuditCommand, arguments: CommandArguments
) -> ChosenAuditInput:
    """Return what ``arguments`` ask to audit, with the warnings it calls for printed.

    Raises ValueError when the staged change cannot be read.
    """
    if arguments.diff_units is not None:
        return await _choose_staged_change(command, arguments.diff_units)
    if arguments.target is not None:
        target = arguments.target
        return ChosenAuditInput(
            audit_input=DiskPathInput(path=target),
            log_directory=target.parent if target.is_file() else target,
        )
    raise ValueError("A path to audit, or --diff, is required")


async def _choose_staged_change(
    command: AuditCommand, diff_units: DiffUnits
) -> ChosenAuditInput:
    staged = await read_staged_change_scope(diff_units, Path.cwd())
    if not staged.has_files():
        print(f"[{command.name}] No staged change to audit", file=sys.stderr)
    for path in staged.paths_with_unstaged_edits:
        print_warning_line(
            command,
            f"'{path}' has unstaged edits too: its units are read from the "
            "working tree, and the changed lines from the index",
        )
    return ChosenAuditInput(
        audit_input=staged.scope.audit_input,
        log_directory=Path.cwd(),
        staged=staged,
    )
