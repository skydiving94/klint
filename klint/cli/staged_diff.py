"""How the klint command words what --diff or --diff-from audited."""

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
