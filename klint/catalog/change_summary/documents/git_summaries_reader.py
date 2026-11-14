"""Reads a summaries-only document, whose change klint reads from git.

The document holds the summaries alone and names the change in
"git_change". Its top level is the root package: its summary is the
commit's. The packages and files it lists are flat; each is placed inside
the deepest listed package that holds it. A hunk is named by its header, as
``git diff -U0`` writes it. A summary the document leaves out is None.
"""

from collections.abc import Container, Mapping, Sequence
from dataclasses import dataclass

from klint.catalog.change_summary.documents.document import (
    ROOT_PACKAGE_PATH,
    SUPPORTED_SCHEMA_VERSION,
    ChangeSummaryDocument,
    is_path_inside_package,
)
from klint.catalog.change_summary.documents.git_summary_tree import (
    FileEntry,
    SummaryEntry,
    build_file_summary,
    build_package_summary,
)
from klint.catalog.change_summary.documents.json_fields import (
    build_document_error,
    list_items,
    read_count,
    read_object,
    read_optional_text,
    read_text,
)
from klint.catalog.domain_neutral.git import (
    GitChange,
    GitFileChange,
    HunkHeader,
    parse_hunk_header,
)
from klint.core.models.reports import JsonValue

# The field that names the change, and so makes a document summaries-only.
GIT_CHANGE_FIELD_NAME = "git_change"
_DOCUMENT_FIELD_NAMES = frozenset(
    {"schema_version", GIT_CHANGE_FIELD_NAME, "summary", "packages", "files"}
)
_GIT_CHANGE_FIELD_NAMES = frozenset({"commit", "base"})
_PACKAGE_FIELD_NAMES = frozenset({"path", "summary"})
_FILE_FIELD_NAMES = frozenset({"path", "summary", "hunks"})
_HUNK_FIELD_NAMES = frozenset({"header", "summary"})
# The most choices an error lists.
_MAX_LISTED_CHOICES = 10


@dataclass(frozen=True)
class GitChangeSelection:
    """The change a summaries-only document summarizes.

    commit names a commit as git names one, such as "HEAD" or a hash. base
    names the commit the change starts from, up to the working tree. Both
    None stands for the uncommitted change.
    """

    commit: str | None
    base: str | None = None


def read_git_change_selection(raw_document: JsonValue) -> GitChangeSelection | None:
    """Return the change ``raw_document`` names; None for a document with code.

    Raises ValueError when the change is named in a way klint cannot read.
    """
    if not isinstance(raw_document, Mapping) or (
        GIT_CHANGE_FIELD_NAME not in raw_document
    ):
        return None
    pointer = f"#/{GIT_CHANGE_FIELD_NAME}"
    git_change = read_object(
        raw_document[GIT_CHANGE_FIELD_NAME], pointer, _GIT_CHANGE_FIELD_NAMES
    )
    commit = read_optional_text(git_change, "commit", pointer)
    base = read_optional_text(git_change, "base", pointer)
    if commit is not None and base is not None:
        raise build_document_error(
            pointer, "names both a commit and a base; give one of them"
        )
    return GitChangeSelection(commit=commit, base=base)


def read_summaries_of_git_change(
    raw_document: JsonValue, change: GitChange
) -> ChangeSummaryDocument:
    """Return the typed document: ``change``, with the summaries ``raw_document`` gives.

    Raises ValueError, naming the place in the document, when a field is of
    the wrong kind, or a summary is about a package, file or hunk the change
    does not hold. Raises ValueError when the change holds no file.
    """
    document = read_object(raw_document, "#", _DOCUMENT_FIELD_NAMES)
    schema_version = read_count(document, "schema_version", "#")
    if schema_version != SUPPORTED_SCHEMA_VERSION:
        raise build_document_error(
            "#/schema_version",
            f"is {schema_version}; klint reads schema_version "
            f"{SUPPORTED_SCHEMA_VERSION} only",
        )
    if not change.files:
        raise ValueError(
            f"The change ({change.diff_command}) holds no changed file, so there "
            "is no summary to verify"
        )
    path_to_file_change = {file.path: file for file in change.files}
    path_to_package_entry = _read_package_entries(document, change)
    path_to_file_entry = _read_file_entries(document, path_to_file_change)
    files = [
        build_file_summary(file, path_to_file_entry.get(file.path))
        for file in change.files
    ]
    return ChangeSummaryDocument(
        schema_version=schema_version,
        diff_command=change.diff_command,
        root_package=build_package_summary(
            ROOT_PACKAGE_PATH,
            SummaryEntry(read_optional_text(document, "summary", "#"), "#"),
            path_to_package_entry,
            files,
        ),
    )


def _read_package_entries(
    document: Mapping[str, JsonValue], change: GitChange
) -> dict[str, SummaryEntry]:
    """Return each listed package's entry, by path, sorted by path."""
    path_to_entry: dict[str, SummaryEntry] = {}
    for raw_package, pointer in list_items(document, "packages", "#", is_optional=True):
        package = read_object(raw_package, pointer, _PACKAGE_FIELD_NAMES)
        path = read_text(package, "path", pointer).rstrip("/")
        if not is_path_inside_package(path, ROOT_PACKAGE_PATH) or not path:
            raise build_document_error(
                f"{pointer}/path",
                f"is '{path}'; a package is a directory inside the repository. "
                "The commit's summary is the document's own summary",
            )
        if not any(is_path_inside_package(file.path, path) for file in change.files):
            raise build_document_error(
                f"{pointer}/path", f"is '{path}', which holds no file of the change"
            )
        _check_new_choice(path, path_to_entry, f"{pointer}/path", "package")
        path_to_entry[path] = SummaryEntry(
            read_optional_text(package, "summary", pointer), pointer
        )
    return dict(sorted(path_to_entry.items()))


def _read_file_entries(
    document: Mapping[str, JsonValue], path_to_file_change: Mapping[str, GitFileChange]
) -> dict[str, FileEntry]:
    """Return each listed file's entry, by path."""
    path_to_entry: dict[str, FileEntry] = {}
    for raw_file, pointer in list_items(document, "files", "#", is_optional=True):
        file = read_object(raw_file, pointer, _FILE_FIELD_NAMES)
        path = read_text(file, "path", pointer)
        file_change = path_to_file_change.get(path)
        if file_change is None:
            raise build_document_error(
                f"{pointer}/path",
                f"is '{path}', which the change does not touch; it touches "
                f"{_list_choices(list(path_to_file_change))}",
            )
        _check_new_choice(path, path_to_entry, f"{pointer}/path", "file")
        path_to_entry[path] = FileEntry(
            own=SummaryEntry(read_optional_text(file, "summary", pointer), pointer),
            header_to_hunk_entry=_read_hunk_entries(file, pointer, file_change),
        )
    return path_to_entry


def _read_hunk_entries(
    file: Mapping[str, JsonValue], file_pointer: str, file_change: GitFileChange
) -> dict[HunkHeader, SummaryEntry]:
    """Return the entry of each hunk the file entry lists, by its header."""
    headers = [hunk.header for hunk in file_change.hunks]
    header_to_entry: dict[HunkHeader, SummaryEntry] = {}
    for raw_hunk, pointer in list_items(file, "hunks", file_pointer, is_optional=True):
        hunk = read_object(raw_hunk, pointer, _HUNK_FIELD_NAMES)
        header_text = read_text(hunk, "header", pointer)
        try:
            header = parse_hunk_header(header_text)
        except ValueError as error:
            raise build_document_error(
                f"{pointer}/header",
                f"is '{header_text}', which is not a hunk header such as "
                "'@@ -20,0 +21 @@', as git diff -U0 writes it",
            ) from error
        if header not in headers:
            hunk_choices = (
                f"its hunks are {_list_choices([h.format_text() for h in headers])}"
                if headers
                else "it has no hunk, as for a binary file or a rename without edits"
            )
            raise build_document_error(
                f"{pointer}/header",
                f"is '{header_text}', which is not a hunk of '{file_change.path}' "
                f"in the change; {hunk_choices}",
            )
        _check_new_choice(header, header_to_entry, f"{pointer}/header", "hunk")
        header_to_entry[header] = SummaryEntry(
            read_optional_text(hunk, "summary", pointer), pointer
        )
    return header_to_entry


def _check_new_choice(
    choice: object, earlier_choices: Container[object], pointer: str, kind: str
) -> None:
    """Raise ValueError when the document named ``choice`` earlier."""
    if choice in earlier_choices:
        raise build_document_error(
            pointer, f"names a {kind} the document has named before"
        )


def _list_choices(choices: Sequence[str]) -> str:
    """Return the choices quoted and joined, the first few only when there are many."""
    listed = ", ".join(f"'{choice}'" for choice in choices[:_MAX_LISTED_CHOICES])
    more_count = len(choices) - _MAX_LISTED_CHOICES
    return f"{listed} and {more_count} more" if more_count > 0 else listed
