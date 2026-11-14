"""Limits an audit to a change: the files it touches, and the units on its lines."""

import os
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from klint.catalog.domain_neutral.file_unit import AuditableFileUnit
from klint.catalog.domain_neutral.git.git_change import (
    ChangeKind,
    GitChange,
    GitFileChange,
    GitHunk,
)
from klint.core.interfaces import BaseUnitSelector
from klint.core.models.audits import DiskFileSetInput
from klint.core.models.units import AuditableUnit


class DiffUnits(StrEnum):
    """Which units of a changed file a change-scoped audit judges."""

    # The file unit, plus every unit whose lines overlap a changed line.
    UNITS = "units"
    # The file units only.
    FILE = "file"
    # Every unit of the changed files.
    ALL = "all"


@dataclass(frozen=True)
class LineSpan:
    """The lines from first_line to last_line, both included."""

    first_line: int
    last_line: int

    def does_overlap(self, other: "LineSpan") -> bool:
        return self.first_line <= other.last_line and other.first_line <= self.last_line


class ChangedUnitSelector(BaseUnitSelector):
    """Keeps the units of changed files that ``diff_units`` asks for.

    path_to_changed_spans gives, for each changed file by its resolved path,
    the spans of its lines the change touches. A unit is matched to its file
    by the path of its location. selected_units holds what the last
    selection kept.
    """

    def __init__(
        self,
        path_to_changed_spans: Mapping[Path, Sequence[LineSpan]],
        diff_units: DiffUnits,
    ) -> None:
        self._path_to_changed_spans = {
            path: tuple(spans) for path, spans in path_to_changed_spans.items()
        }
        self._diff_units = diff_units
        self.selected_units: list[AuditableUnit] = []

    def select_units(self, units: Sequence[AuditableUnit]) -> list[AuditableUnit]:
        self.selected_units = [unit for unit in units if self._does_keep(unit)]
        return list(self.selected_units)

    def _does_keep(self, unit: AuditableUnit) -> bool:
        is_file_unit = isinstance(unit, AuditableFileUnit)
        match self._diff_units:
            case DiffUnits.ALL:
                return True
            case DiffUnits.FILE:
                return is_file_unit
            case DiffUnits.UNITS:
                return is_file_unit or self._does_overlap_a_change(unit)

    def _does_overlap_a_change(self, unit: AuditableUnit) -> bool:
        location = unit.get_location()
        if location is None or location.line_range is None:
            return False
        unit_span = LineSpan(*location.line_range)
        changed_spans = self._path_to_changed_spans.get(
            Path(location.path).resolve(), ()
        )
        return any(unit_span.does_overlap(span) for span in changed_spans)


@dataclass(frozen=True)
class ChangeScope:
    """What an audit limited to a change goes through.

    audit_input lists the changed files to read, each by the path the audit
    names it by. unit_selector keeps the units asked for among theirs.
    deleted_paths are the files the change deletes, which are not audited.
    """

    audit_input: DiskFileSetInput
    unit_selector: ChangedUnitSelector
    deleted_paths: tuple[str, ...]

    def list_audited_paths(self) -> list[str]:
        """Return the path of each changed file to audit, as the audit names it."""
        return [str(path) for path in self.audit_input.paths]


def scope_audit_to_change(
    change: GitChange, diff_units: DiffUnits, working_directory: Path
) -> ChangeScope:
    """Return the scope of an audit of ``change`` limited to ``diff_units``.

    A deleted file is left out, and a renamed one is audited under its new
    path. Each file is named by its path relative to ``working_directory``,
    as a target given on a command line would be.
    """
    path_to_changed_spans: dict[Path, tuple[LineSpan, ...]] = {}
    audited_paths: list[Path] = []
    deleted_paths: list[str] = []
    for file_change in change.files:
        if file_change.change_kind is ChangeKind.DELETED:
            deleted_paths.append(file_change.path)
            continue
        absolute_path = change.repository_path / file_change.path
        audited_paths.append(Path(os.path.relpath(absolute_path, working_directory)))
        path_to_changed_spans[absolute_path.resolve()] = _list_changed_spans(
            file_change
        )
    return ChangeScope(
        audit_input=DiskFileSetInput(
            root=change.repository_path, paths=tuple(audited_paths)
        ),
        unit_selector=ChangedUnitSelector(path_to_changed_spans, diff_units),
        deleted_paths=tuple(deleted_paths),
    )


def _list_changed_spans(file_change: GitFileChange) -> tuple[LineSpan, ...]:
    """Return the spans of the file's lines, after the change, that it touches."""
    return tuple(_find_changed_span(hunk) for hunk in file_change.hunks)


def _find_changed_span(hunk: GitHunk) -> LineSpan:
    """Return the lines ``hunk`` adds; for a pure deletion, the lines around it.

    A hunk that only removes lines names, as its new start, the line before
    the removal; it touches that line and the one after it.
    """
    header = hunk.header
    if header.new_line_count == 0:
        return LineSpan(max(header.new_start, 1), header.new_start + 1)
    return LineSpan(header.new_start, header.new_start + header.new_line_count - 1)
