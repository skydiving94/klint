"""Reads a parsed change-summary document into its typed model, checking its shape.

A place in the document is named by a JSON pointer, written as a URI
fragment: "#/root_package/files/0/summary".
"""

import warnings
from collections.abc import Mapping, Sequence
from typing import TypeGuard

from klint.catalog.change_summary.document import (
    SUPPORTED_SCHEMA_VERSION,
    ChangeKind,
    ChangeSummaryDocument,
    FileSummary,
    HunkSummary,
    PackageSummary,
)
from klint.core.klint_warning import KlintWarning
from klint.core.models.json_value import JsonValue

# The path of the root package: the directory the change is in.
ROOT_PACKAGE_PATH = "."
_DOCUMENT_FIELD_NAMES = frozenset({"schema_version", "diff_command", "root_package"})
_PACKAGE_FIELD_NAMES = frozenset({"path", "summary", "packages", "files"})
_FILE_FIELD_NAMES = frozenset({"path", "old_path", "change_kind", "summary", "hunks"})
_HUNK_FIELD_NAMES = frozenset(
    {
        "hunk_id",
        "old_start",
        "old_line_count",
        "new_start",
        "new_line_count",
        "removed_lines",
        "added_lines",
        "summary",
    }
)


def read_change_summary_document(raw_document: JsonValue) -> ChangeSummaryDocument:
    """Return the typed document that ``raw_document``, parsed JSON, holds.

    Raises ValueError, naming the place in the document, when a field is
    missing or of the wrong kind, the schema version is not supported, a
    hunk's lines do not match its line counts, or a file or package is not
    inside its package. An unknown field is reported as a KlintWarning and ignored.
    """
    return _read_document(raw_document)


def _read_document(raw_document: JsonValue) -> ChangeSummaryDocument:
    document = _read_object(raw_document, "#", _DOCUMENT_FIELD_NAMES)
    schema_version = _read_count(document, "schema_version", "#")
    if schema_version != SUPPORTED_SCHEMA_VERSION:
        raise _build_error(
            "#/schema_version",
            f"is {schema_version}; klint reads schema_version "
            f"{SUPPORTED_SCHEMA_VERSION} only",
        )
    return ChangeSummaryDocument(
        schema_version=schema_version,
        diff_command=_read_text(document, "diff_command", "#"),
        root_package=_read_package(
            _read_field(document, "root_package", "#"), "#/root_package", None
        ),
    )


def _read_package(
    raw_package: JsonValue, pointer: str, parent_path: str | None
) -> PackageSummary:
    package = _read_object(raw_package, pointer, _PACKAGE_FIELD_NAMES)
    path = _read_text(package, "path", pointer).rstrip("/") or ROOT_PACKAGE_PATH
    if parent_path is None and path != ROOT_PACKAGE_PATH:
        raise _build_error(
            f"{pointer}/path",
            f"is '{path}'; the root package is '{ROOT_PACKAGE_PATH}', the "
            "directory the change is in",
        )
    if parent_path is not None and not _is_strictly_inside(path, parent_path):
        raise _build_error(
            f"{pointer}/path",
            f"is '{path}', which is not inside its package '{parent_path}'",
        )
    return PackageSummary(
        path=path,
        summary=_read_text(package, "summary", pointer),
        packages=tuple(
            _read_package(raw, item_pointer, path)
            for raw, item_pointer in _list_items(package, "packages", pointer)
        ),
        files=tuple(
            _read_file(raw, item_pointer, path)
            for raw, item_pointer in _list_items(package, "files", pointer)
        ),
        pointer=pointer,
    )


def _read_file(raw_file: JsonValue, pointer: str, package_path: str) -> FileSummary:
    file = _read_object(raw_file, pointer, _FILE_FIELD_NAMES)
    path = _read_text(file, "path", pointer)
    if not _is_strictly_inside(path, package_path):
        raise _build_error(
            f"{pointer}/path",
            f"is '{path}', which is not inside its package '{package_path}'",
        )
    change_kind = _read_change_kind(file, pointer)
    return FileSummary(
        path=path,
        old_path=_read_old_path(file, pointer, change_kind),
        change_kind=change_kind,
        summary=_read_text(file, "summary", pointer),
        hunks=tuple(
            _read_hunk(raw, item_pointer)
            for raw, item_pointer in _list_items(file, "hunks", pointer)
        ),
        pointer=pointer,
    )


def _read_hunk(raw_hunk: JsonValue, pointer: str) -> HunkSummary:
    hunk = _read_object(raw_hunk, pointer, _HUNK_FIELD_NAMES)
    hunk_id = _read_text(hunk, "hunk_id", pointer)
    old_line_count = _read_count(hunk, "old_line_count", pointer)
    new_line_count = _read_count(hunk, "new_line_count", pointer)
    if old_line_count == 0 and new_line_count == 0:
        raise _build_error(pointer, "removes no line and adds none")
    return HunkSummary(
        hunk_id=hunk_id,
        old_start=_read_count(hunk, "old_start", pointer),
        old_line_count=old_line_count,
        new_start=_read_count(hunk, "new_start", pointer),
        new_line_count=new_line_count,
        removed_lines=_read_lines(hunk, "removed_lines", pointer, old_line_count),
        added_lines=_read_lines(hunk, "added_lines", pointer, new_line_count),
        summary=_read_text(hunk, "summary", pointer),
        pointer=pointer,
    )


def _build_error(pointer: str, problem: str) -> ValueError:
    return ValueError(f"Change-summary document: {pointer} {problem}")


def _read_object(
    raw_value: JsonValue, pointer: str, field_names: frozenset[str]
) -> Mapping[str, JsonValue]:
    """Return ``raw_value`` as an object; warn about fields not in ``field_names``."""
    if not isinstance(raw_value, Mapping):
        raise _build_error(pointer, "must be a JSON object")
    unknown_field_names = sorted(set(raw_value) - field_names)
    if unknown_field_names:
        warnings.warn(
            f"Change-summary document: {pointer} has unknown fields "
            f"{unknown_field_names}, which are ignored; known fields: "
            f"{sorted(field_names)}",
            KlintWarning,
            stacklevel=2,
        )
    return raw_value


def _read_field(
    raw_object: Mapping[str, JsonValue], field_name: str, pointer: str
) -> JsonValue:
    if field_name not in raw_object:
        raise _build_error(f"{pointer}/{field_name}", "is missing")
    return raw_object[field_name]


def _read_text(
    raw_object: Mapping[str, JsonValue], field_name: str, pointer: str
) -> str:
    """Return the field as text that is not blank."""
    raw_value = _read_field(raw_object, field_name, pointer)
    if not isinstance(raw_value, str) or not raw_value.strip():
        raise _build_error(f"{pointer}/{field_name}", "must be text that is not blank")
    return raw_value


def _read_count(
    raw_object: Mapping[str, JsonValue], field_name: str, pointer: str
) -> int:
    """Return the field as a whole number of at least 0."""
    raw_value = _read_field(raw_object, field_name, pointer)
    if isinstance(raw_value, bool) or not isinstance(raw_value, int) or raw_value < 0:
        raise _build_error(
            f"{pointer}/{field_name}", "must be a whole number of at least 0"
        )
    return raw_value


def _read_lines(
    raw_object: Mapping[str, JsonValue],
    field_name: str,
    pointer: str,
    line_count: int,
) -> tuple[str, ...]:
    """Return the field as a list of ``line_count`` lines of text."""
    raw_value = _read_field(raw_object, field_name, pointer)
    if not _is_list_of_text(raw_value):
        raise _build_error(f"{pointer}/{field_name}", "must be a list of text lines")
    if len(raw_value) != line_count:
        raise _build_error(
            f"{pointer}/{field_name}",
            f"holds {len(raw_value)} lines, but the hunk's line count is {line_count}",
        )
    return tuple(raw_value)


def _list_items(
    raw_object: Mapping[str, JsonValue], field_name: str, pointer: str
) -> list[tuple[JsonValue, str]]:
    """Return each item of the list in the field, with its pointer."""
    raw_value = _read_field(raw_object, field_name, pointer)
    if not isinstance(raw_value, Sequence) or isinstance(raw_value, str):
        raise _build_error(f"{pointer}/{field_name}", "must be a list")
    return [
        (item, f"{pointer}/{field_name}/{index}")
        for index, item in enumerate(raw_value)
    ]


def _read_change_kind(raw_file: Mapping[str, JsonValue], pointer: str) -> ChangeKind:
    raw_value = _read_field(raw_file, "change_kind", pointer)
    for change_kind in ChangeKind:
        if raw_value == change_kind.value:
            return change_kind
    raise _build_error(
        f"{pointer}/change_kind",
        f"is {raw_value!r}; known kinds: {[kind.value for kind in ChangeKind]}",
    )


def _read_old_path(
    raw_file: Mapping[str, JsonValue], pointer: str, change_kind: ChangeKind
) -> str | None:
    """Return the path before a rename; None, and absent or null, for other kinds."""
    raw_value = raw_file.get("old_path")
    if change_kind is ChangeKind.RENAMED:
        if not isinstance(raw_value, str) or not raw_value.strip():
            raise _build_error(
                f"{pointer}/old_path", "must be the path before the rename"
            )
        return raw_value
    if raw_value is not None:
        raise _build_error(
            f"{pointer}/old_path",
            f"is set for a file that is {change_kind.value}; only a renamed "
            "file has one",
        )
    return None


def _is_strictly_inside(path: str, package_path: str) -> bool:
    """Return True when ``path`` is below the directory ``package_path``."""
    if package_path == ROOT_PACKAGE_PATH:
        return path != ROOT_PACKAGE_PATH and not path.startswith(("/", "../"))
    return path.startswith(f"{package_path}/")


def _is_list_of_text(raw_value: JsonValue) -> TypeGuard[list[str]]:
    return isinstance(raw_value, list) and all(
        isinstance(item, str) for item in raw_value
    )
