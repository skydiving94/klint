"""How the klint command words what --diff audited."""

from klint.app.staged_change import StagedChangeScope


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
