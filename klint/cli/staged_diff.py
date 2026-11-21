"""How the klint commands word what --diff or --diff-from audited."""

from klint.app.changed_directories import ChangedDirectoriesScope
from klint.catalog.domain_neutral.git import ChangeScope, DiffUnits


def describe_change_scope(
    scope: ChangeScope,
    diff_units: DiffUnits,
    extracted_unit_count: int,
    selected_unit_count: int,
) -> str:
    """Say what an audit of a change covered, for the end of the run.

    For example "3 files, 5 of 12 units selected (--diff-units units); 1
    deleted file skipped".
    """
    file_count = len(scope.audit_input.paths)
    file_noun = "file" if file_count == 1 else "files"
    unit_noun = "unit" if extracted_unit_count == 1 else "units"
    text = (
        f"{file_count} {file_noun}, {selected_unit_count} of {extracted_unit_count} "
        f"{unit_noun} selected (--diff-units {diff_units.value})"
    )
    deleted_count = len(scope.deleted_paths)
    if deleted_count:
        deleted_noun = "file" if deleted_count == 1 else "files"
        text += f"; {deleted_count} deleted {deleted_noun} skipped"
    return text


def describe_changed_directories(scope: ChangedDirectoriesScope) -> str:
    """Say what a structure audit of a change covered, for the end of the run.

    For example "3 files, 4 of 12 directories selected; 1 deleted file", or
    "1 file, in no directory the audit covers".
    """
    file_count = len(scope.changed_paths)
    text = f"{file_count} {_name_files(file_count)}"
    deleted_count = len(scope.deleted_paths)
    if deleted_count:
        text += f" and {deleted_count} deleted {_name_files(deleted_count)}"
    selector = scope.unit_selector
    directory_count = len(selector.selected_units)
    if not directory_count:
        return f"{text}, in no directory the audit covers"
    offered_noun = (
        "directory" if selector.offered_directory_count == 1 else "directories"
    )
    return (
        f"{text}, {directory_count} of {selector.offered_directory_count} "
        f"{offered_noun} selected"
    )


def _name_files(count: int) -> str:
    return "file" if count == 1 else "files"
