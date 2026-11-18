"""A structure audit of what a unified diff touches: the directories that hold it."""

import os
from dataclasses import dataclass
from pathlib import Path

from klint.app.diff_change import (
    is_unchecked_against_disk,
    read_files_checked_against_disk,
)
from klint.catalog.domain_neutral import ChangedDirectorySelector
from klint.catalog.domain_neutral.git import ChangeKind, GitFileChange
from klint.core.models.audits import DiskPathInput
from klint.core.models.reports import JsonValue
from klint.core.models.scanning import IgnoredNames


@dataclass(frozen=True)
class ChangedDirectoriesScope:
    """The change a diff describes, as a structure audit of it goes through it.

    audit_input is the whole project, so that each directory is summarized as
    in a full audit; unit_selector keeps the directories that hold a changed
    path, and their parents. changed_paths are the files the change leaves on
    disk, and deleted_paths the ones it deletes, each as the diff names it.
    is_unchecked_against_disk is true when the diff has no index lines, so
    that no file on disk could be checked against it.
    """

    audit_input: DiskPathInput
    unit_selector: ChangedDirectorySelector
    changed_paths: tuple[str, ...]
    deleted_paths: tuple[str, ...]
    is_unchecked_against_disk: bool

    def has_files(self) -> bool:
        return bool(self.changed_paths or self.deleted_paths)

    def list_audited_directories(self) -> list[str]:
        """Return the path of each directory the audit kept, parents first."""
        locations = (unit.get_location() for unit in self.unit_selector.selected_units)
        return [location.path for location in locations if location is not None]


async def read_changed_directories_scope(
    diff_text: str, working_directory: Path, ignored_names: IgnoredNames
) -> ChangedDirectoriesScope:
    """Return the scope of a structure audit of what ``diff_text`` changes.

    The project is ``working_directory``, and the diff's paths are taken as
    relative to it. ``ignored_names`` are the names the audit's scan leaves
    out. Raises ValueError when the diff cannot be read, names a
    file outside ``working_directory``, or names a file whose content on disk
    is not the one its index line gives.
    """
    files = await read_files_checked_against_disk(diff_text, working_directory)
    # The project is named as a full audit run from it names it, so that the
    # units, and the answers cached for them, are the same.
    project = Path(os.path.relpath(working_directory, Path.cwd()))
    return ChangedDirectoriesScope(
        audit_input=DiskPathInput(path=project),
        unit_selector=ChangedDirectorySelector(
            [project / path for path in _list_touched_paths(files)],
            ignored_names,
        ),
        changed_paths=tuple(
            file_change.path
            for file_change in files
            if file_change.change_kind is not ChangeKind.DELETED
        ),
        deleted_paths=tuple(
            file_change.path
            for file_change in files
            if file_change.change_kind is ChangeKind.DELETED
        ),
        is_unchecked_against_disk=is_unchecked_against_disk(files),
    )


def convert_changed_directories_to_dict(
    scope: ChangedDirectoriesScope, extracted_unit_count: int, selected_unit_count: int
) -> dict[str, JsonValue]:
    """Return what the structure audit of the diff covered, as JSON output writes it.

    The CLI writes it under "diff_change" with --diff-from.
    """
    return {
        "files": list(scope.changed_paths),
        "deleted_files": list(scope.deleted_paths),
        "unit_count": extracted_unit_count,
        "selected_unit_count": selected_unit_count,
        "audited_directories": list(scope.list_audited_directories()),
    }


def _list_touched_paths(files: tuple[GitFileChange, ...]) -> list[str]:
    """Return each path the change touches: a renamed file's old path too."""
    paths: list[str] = []
    for file_change in files:
        paths.append(file_change.path)
        if file_change.old_path is not None:
            paths.append(file_change.old_path)
    return paths
