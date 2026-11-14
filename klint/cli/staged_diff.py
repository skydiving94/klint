"""The klint command on the staged change: what --diff reads, keeps and says."""

from dataclasses import asdict, dataclass
from pathlib import Path

from klint.catalog.domain_neutral.git import (
    ChangeScope,
    DiffUnits,
    GitChangeSource,
    scope_audit_to_change,
)
from klint.core.models.reports import JsonValue
from klint.core.models.units import AuditableUnit


@dataclass(frozen=True)
class StagedChangeScope:
    """The staged change as --diff audits it.

    scope is what the audit goes through. diff_units is the choice of units
    made. paths_with_unstaged_edits are the audited files whose working tree
    differs from the index: their units are read from the working tree,
    while the changed lines come from the index.
    """

    scope: ChangeScope
    diff_units: DiffUnits
    paths_with_unstaged_edits: tuple[str, ...]

    def has_files(self) -> bool:
        return bool(self.scope.audit_input.paths)


async def read_staged_change_scope(
    diff_units: DiffUnits, working_directory: Path
) -> StagedChangeScope:
    """Return the scope of an audit of the staged change in ``working_directory``.

    Raises ValueError when the directory is not in a git repository or git
    cannot be run.
    """
    source = GitChangeSource(working_directory, is_staged=True)
    change = await source.read_input()
    scope = scope_audit_to_change(change, diff_units, working_directory)
    audited_paths = {
        file_change.path
        for file_change in change.files
        if file_change.path not in scope.deleted_paths
    }
    unstaged_paths = await source.list_paths_with_unstaged_edits()
    return StagedChangeScope(
        scope=scope,
        diff_units=diff_units,
        paths_with_unstaged_edits=tuple(
            path for path in unstaged_paths if path in audited_paths
        ),
    )


def describe_staged_change(
    staged: StagedChangeScope, extracted_unit_count: int, selected_unit_count: int
) -> str:
    """Say what --diff audited, for the end of the run.

    For example "3 files, 5 of 12 units selected (--diff-units units); 1
    deleted file skipped".
    """
    file_count = len(staged.scope.audit_input.paths)
    file_noun = "file" if file_count == 1 else "files"
    unit_noun = "unit" if extracted_unit_count == 1 else "units"
    text = (
        f"{file_count} {file_noun}, {selected_unit_count} of {extracted_unit_count} "
        f"{unit_noun} selected (--diff-units {staged.diff_units.value})"
    )
    deleted_count = len(staged.scope.deleted_paths)
    if deleted_count:
        deleted_noun = "file" if deleted_count == 1 else "files"
        text += f"; {deleted_count} deleted {deleted_noun} skipped"
    return text


def convert_staged_change_to_dict(
    staged: StagedChangeScope, extracted_unit_count: int, selected_unit_count: int
) -> dict[str, JsonValue]:
    """Return what --diff audited, as --json writes it under "staged_change"."""
    return {
        "diff_units": staged.diff_units.value,
        "files": list(staged.scope.list_audited_paths()),
        "deleted_files": list(staged.scope.deleted_paths),
        "unit_count": extracted_unit_count,
        "selected_unit_count": selected_unit_count,
        "selected_units": [
            _convert_unit_to_dict(unit)
            for unit in staged.scope.unit_selector.selected_units
        ],
    }


def _convert_unit_to_dict(unit: AuditableUnit) -> dict[str, JsonValue]:
    """Return a selected unit as --json lists it: its ID, type, place and context."""
    location = unit.get_location()
    return {
        "unit_id": unit.unit_id,
        "unit_type": unit.unit_type,
        "location": None if location is None else asdict(location),
        "context": asdict(unit.get_context()),
    }
