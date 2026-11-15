"""An audit of what a unified diff touches: what --diff-from reads and keeps."""

from dataclasses import dataclass
from pathlib import Path

from klint.app.change_scope_json import convert_change_scope_to_dict
from klint.catalog.domain_neutral.git import (
    ChangeKind,
    ChangeScope,
    DiffUnits,
    GitChange,
    GitFileChange,
    find_blob_hash_mismatches,
    parse_git_diff,
    scope_audit_to_change,
)
from klint.core.models.reports import JsonValue


@dataclass(frozen=True)
class DiffChangeScope:
    """The change a diff describes, as --diff-from audits it.

    scope is what the audit goes through. diff_units is the choice of units
    made. is_unchecked_against_disk is true when the diff has no index lines, so that no
    file on disk could be checked against it.
    """

    scope: ChangeScope
    diff_units: DiffUnits
    is_unchecked_against_disk: bool

    def has_files(self) -> bool:
        return bool(self.scope.audit_input.paths)


async def read_diff_change_scope(
    diff_text: str, diff_units: DiffUnits, working_directory: Path
) -> DiffChangeScope:
    """Return the scope of an audit of what ``diff_text`` changes.

    The diff's paths are taken as relative to ``working_directory``, and each
    changed file is read from there. Raises ValueError when the diff cannot be
    read, names a file outside ``working_directory``, or names a file whose
    content on disk is not the one its index line gives.
    """
    files = tuple(parse_git_diff(diff_text))
    for file_change in files:
        _check_path_is_inside(file_change, working_directory)
    mismatches = await find_blob_hash_mismatches(files, working_directory)
    if mismatches:
        described = "; ".join(mismatch.describe() for mismatch in mismatches)
        raise ValueError(
            "The diff does not match the files on disk, so its changed lines "
            f"cannot be found in them: {described}"
        )
    change = GitChange(
        repository_path=working_directory, diff_command="--diff-from", files=files
    )
    return DiffChangeScope(
        scope=scope_audit_to_change(change, diff_units, working_directory),
        diff_units=diff_units,
        is_unchecked_against_disk=bool(files)
        and all(file_change.new_blob_hash is None for file_change in files),
    )


def convert_diff_change_to_dict(
    diff_change: DiffChangeScope, extracted_unit_count: int, selected_unit_count: int
) -> dict[str, JsonValue]:
    """Return what the audit of the diff covered, as JSON output writes it.

    The CLI writes it under "diff_change" with --diff-from.
    """
    return convert_change_scope_to_dict(
        diff_change.scope,
        diff_change.diff_units,
        extracted_unit_count,
        selected_unit_count,
    )


def _check_path_is_inside(file_change: GitFileChange, working_directory: Path) -> None:
    """Raise ValueError when the file is outside ``working_directory``."""
    if file_change.change_kind is ChangeKind.DELETED:
        return
    directory = working_directory.resolve()
    if not (directory / file_change.path).resolve().is_relative_to(directory):
        raise ValueError(
            f"The diff changes '{file_change.path}', which is outside the current "
            f"directory '{directory}'"
        )
