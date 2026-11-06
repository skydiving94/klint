"""Reads a change-summary document that holds each hunk's code beside its summary.

A place in the document is named by a JSON pointer, written as a URI
fragment: "#/root_package/files/0/summary".
"""

from collections.abc import Mapping
from typing import TypeGuard

from klint.catalog.change_summary.documents.document import (
    ROOT_PACKAGE_PATH,
    SUPPORTED_SCHEMA_VERSION,
    ChangeKind,
    ChangeSummaryDocument,
    FileSummary,
    HunkSummary,
    PackageSummary,
    is_path_inside_package,
)
from klint.catalog.change_summary.documents.json_fields import (
    build_document_error,
    list_items,
    read_count,
    read_field,
    read_object,
    read_text,
)
from klint.catalog.domain_neutral.git import HunkHeader
from klint.core.models.reports import JsonValue

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
    document = read_object(raw_document, "#", _DOCUMENT_FIELD_NAMES)
    schema_version = read_count(document, "schema_version", "#")
    if schema_version != SUPPORTED_SCHEMA_VERSION:
        raise build_document_error(
            "#/schema_version",
            f"is {schema_version}; klint reads schema_version "
            f"{SUPPORTED_SCHEMA_VERSION} only",
        )
    return ChangeSummaryDocument(
        schema_version=schema_version,
        diff_command=read_text(document, "diff_command", "#"),
        root_package=_read_package(
            read_field(document, "root_package", "#"), "#/root_package", None
        ),
    )


def _read_package(
    raw_package: JsonValue, pointer: str, parent_path: str | None
) -> PackageSummary:
    package = read_object(raw_package, pointer, _PACKAGE_FIELD_NAMES)
    path = read_text(package, "path", pointer).rstrip("/") or ROOT_PACKAGE_PATH
    if parent_path is None and path != ROOT_PACKAGE_PATH:
        raise build_document_error(
            f"{pointer}/path",
            f"is '{path}'; the root package is '{ROOT_PACKAGE_PATH}', the "
            "directory the change is in",
        )
    if parent_path is not None and not is_path_inside_package(path, parent_path):
        raise build_document_error(
            f"{pointer}/path",
            f"is '{path}', which is not inside its package '{parent_path}'",
        )
    return PackageSummary(
        path=path,
        summary=read_text(package, "summary", pointer),
        packages=tuple(
            _read_package(raw, item_pointer, path)
            for raw, item_pointer in list_items(package, "packages", pointer)
        ),
        files=tuple(
            _read_file(raw, item_pointer, path)
            for raw, item_pointer in list_items(package, "files", pointer)
        ),
        pointer=pointer,
    )


def _read_file(raw_file: JsonValue, pointer: str, package_path: str) -> FileSummary:
    file = read_object(raw_file, pointer, _FILE_FIELD_NAMES)
    path = read_text(file, "path", pointer)
    if not is_path_inside_package(path, package_path):
        raise build_document_error(
            f"{pointer}/path",
            f"is '{path}', which is not inside its package '{package_path}'",
        )
    change_kind = _read_change_kind(file, pointer)
    return FileSummary(
        path=path,
        old_path=_read_old_path(file, pointer, change_kind),
        change_kind=change_kind,
        summary=read_text(file, "summary", pointer),
        hunks=tuple(
            _read_hunk(raw, item_pointer)
            for raw, item_pointer in list_items(file, "hunks", pointer)
        ),
        pointer=pointer,
    )


def _read_hunk(raw_hunk: JsonValue, pointer: str) -> HunkSummary:
    hunk = read_object(raw_hunk, pointer, _HUNK_FIELD_NAMES)
    hunk_id = read_text(hunk, "hunk_id", pointer)
    old_line_count = read_count(hunk, "old_line_count", pointer)
    new_line_count = read_count(hunk, "new_line_count", pointer)
    if old_line_count == 0 and new_line_count == 0:
        raise build_document_error(pointer, "removes no line and adds none")
    return HunkSummary(
        hunk_id=hunk_id,
        header=HunkHeader(
            old_start=read_count(hunk, "old_start", pointer),
            old_line_count=old_line_count,
            new_start=read_count(hunk, "new_start", pointer),
            new_line_count=new_line_count,
        ),
        removed_lines=_read_lines(hunk, "removed_lines", pointer, old_line_count),
        added_lines=_read_lines(hunk, "added_lines", pointer, new_line_count),
        summary=read_text(hunk, "summary", pointer),
        pointer=pointer,
    )


def _read_lines(
    raw_object: Mapping[str, JsonValue],
    field_name: str,
    pointer: str,
    line_count: int,
) -> tuple[str, ...]:
    """Return the field as a list of ``line_count`` lines of text."""
    raw_value = read_field(raw_object, field_name, pointer)
    if not _is_list_of_text(raw_value):
        raise build_document_error(
            f"{pointer}/{field_name}", "must be a list of text lines"
        )
    if len(raw_value) != line_count:
        raise build_document_error(
            f"{pointer}/{field_name}",
            f"holds {len(raw_value)} lines, but the hunk's line count is {line_count}",
        )
    return tuple(raw_value)


def _read_change_kind(raw_file: Mapping[str, JsonValue], pointer: str) -> ChangeKind:
    raw_value = read_field(raw_file, "change_kind", pointer)
    for change_kind in ChangeKind:
        if raw_value == change_kind.value:
            return change_kind
    raise build_document_error(
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
            raise build_document_error(
                f"{pointer}/old_path", "must be the path before the rename"
            )
        return raw_value
    if raw_value is not None:
        raise build_document_error(
            f"{pointer}/old_path",
            f"is set for a file that is {change_kind.value}; only a renamed "
            "file has one",
        )
    return None


def _is_list_of_text(raw_value: JsonValue) -> TypeGuard[list[str]]:
    return isinstance(raw_value, list) and all(
        isinstance(item, str) for item in raw_value
    )
