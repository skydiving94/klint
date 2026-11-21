"""What a klint command audits: a path, the staged change, or a diff's change."""

import sys
from dataclasses import dataclass
from pathlib import Path

from klint.app.changed_directories import (
    ChangedDirectoriesScope,
    read_changed_directories_scope,
)
from klint.app.diff_change import DiffChangeScope, read_diff_change_scope
from klint.app.staged_change import StagedChangeScope, read_staged_change_scope
from klint.catalog.code.language_neutral import CODE_IGNORED_NAMES
from klint.catalog.domain_neutral.git import DiffUnits
from klint.cli.audit_command import AuditCommand, DiffOptions
from klint.cli.command_arguments import CommandArguments
from klint.cli.console import print_warning_line
from klint.cli.staged_diff import (
    describe_change_scope,
    describe_changed_directories,
)
from klint.core.interfaces import BaseUnitSelector
from klint.core.models.audits import AuditInput, DiskPathInput

_STDIN_PATH = Path("-")


@dataclass(frozen=True)
class ChosenAuditInput:
    """What one run audits, and where its acknowledgement log is looked for.

    staged is the staged change, when the run audits it, and diff_change the
    change a diff describes, when the run audits that: its units, or the
    directories that hold it for a structure audit. Both None for a path.
    """

    audit_input: AuditInput
    log_directory: Path
    staged: StagedChangeScope | None = None
    diff_change: DiffChangeScope | ChangedDirectoriesScope | None = None

    def find_unit_selector(self) -> BaseUnitSelector | None:
        """Return what keeps the units of the change; None for a path."""
        if self.staged is not None:
            return self.staged.scope.unit_selector
        if isinstance(self.diff_change, DiffChangeScope):
            return self.diff_change.scope.unit_selector
        if self.diff_change is not None:
            return self.diff_change.unit_selector
        return None

    def describe_change(
        self, extracted_unit_count: int, selected_unit_count: int
    ) -> str | None:
        """Say what the audit of the change covered; None for a path.

        For example "Staged change: 1 file, 3 of 5 units selected
        (--diff-units units)".
        """
        if self.staged is not None:
            description = describe_change_scope(
                self.staged.scope,
                self.staged.diff_units,
                extracted_unit_count,
                selected_unit_count,
            )
            return f"Staged change: {description}"
        if isinstance(self.diff_change, ChangedDirectoriesScope):
            return (
                f"Change in the diff: {describe_changed_directories(self.diff_change)}"
            )
        if self.diff_change is not None:
            description = describe_change_scope(
                self.diff_change.scope,
                self.diff_change.diff_units,
                extracted_unit_count,
                selected_unit_count,
            )
            return f"Change in the diff: {description}"
        return None


async def choose_audit_input(
    command: AuditCommand, arguments: CommandArguments
) -> ChosenAuditInput:
    """Return what ``arguments`` ask to audit, with the warnings it calls for printed.

    Raises ValueError when the staged change or the diff cannot be read.
    """
    if (
        command.diff_options is DiffOptions.CHANGED_DIRECTORIES
        and arguments.diff_from is not None
    ):
        return await _choose_changed_directories(command, arguments.diff_from)
    if arguments.diff_units is not None and arguments.diff_from is not None:
        return await _choose_diff_change(
            command, arguments.diff_from, arguments.diff_units
        )
    if arguments.diff_units is not None:
        return await _choose_staged_change(command, arguments.diff_units)
    if arguments.target is not None:
        target = arguments.target
        return ChosenAuditInput(
            audit_input=DiskPathInput(path=target),
            log_directory=target.parent if target.is_file() else target,
        )
    raise ValueError("A path to audit, --diff or --diff-from is required")


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


async def _choose_diff_change(
    command: AuditCommand, diff_from: Path, diff_units: DiffUnits
) -> ChosenAuditInput:
    diff_change = await read_diff_change_scope(
        _read_diff_text(diff_from), diff_units, Path.cwd()
    )
    if not diff_change.has_files():
        print(f"[{command.name}] No change in the diff to audit", file=sys.stderr)
    if diff_change.is_unchecked_against_disk:
        _warn_about_unchecked_diff(command)
    return ChosenAuditInput(
        audit_input=diff_change.scope.audit_input,
        log_directory=Path.cwd(),
        diff_change=diff_change,
    )


async def _choose_changed_directories(
    command: AuditCommand, diff_from: Path
) -> ChosenAuditInput:
    changed_directories = await read_changed_directories_scope(
        _read_diff_text(diff_from), Path.cwd(), CODE_IGNORED_NAMES
    )
    if not changed_directories.has_files():
        print(f"[{command.name}] No change in the diff to audit", file=sys.stderr)
    if changed_directories.is_unchecked_against_disk:
        _warn_about_unchecked_diff(command)
    return ChosenAuditInput(
        audit_input=changed_directories.audit_input,
        log_directory=Path.cwd(),
        diff_change=changed_directories,
    )


def _warn_about_unchecked_diff(command: AuditCommand) -> None:
    print_warning_line(
        command,
        "the diff has no index lines, so the files on disk are taken as "
        "the ones it changes, unchecked",
    )


def _read_diff_text(diff_from: Path) -> str:
    """Return the diff in the file ``diff_from``, or on stdin for "-".

    Raises ValueError when the file cannot be read.
    """
    if diff_from == _STDIN_PATH:
        diff_bytes = sys.stdin.buffer.read()
    else:
        try:
            diff_bytes = diff_from.read_bytes()
        except OSError as error:
            raise ValueError(
                f"Cannot read the diff '{diff_from}': {error.strerror}"
            ) from error
    return diff_bytes.decode("utf-8", errors="replace")
