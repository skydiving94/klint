"""Whether a summaries document names the files and hunks of the current change.

A document names what it summarizes by path and by hunk header. It is of
the current change when it names each changed file and each of their
hunks, and nothing else. A field that cannot be read is skipped here; the
document's reader reports it.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from klint.catalog.domain_neutral.git import (
    GitChange,
    GitFileChange,
    HunkHeader,
    parse_hunk_header,
)
from klint.core.models.reports import JsonValue


@dataclass(frozen=True)
class NamedFile:
    """A file a document lists, and the headers of the hunks it lists for it."""

    path: str
    headers: frozenset[HunkHeader]


@dataclass(frozen=True)
class SummaryCoverage:
    """What the change holds that the document does not name, and the reverse.

    unnamed_parts and stale_parts each describe one file or hunk, such as
    "app/greet.py" or "app/greet.py @@ -5 +4,2 @@".
    """

    unnamed_parts: tuple[str, ...]
    stale_parts: tuple[str, ...]

    def is_complete(self) -> bool:
        """Return True when the document names exactly the change's files and hunks."""
        return not self.unnamed_parts and not self.stale_parts


def compare_summaries_with_change(
    raw_document: JsonValue, change: GitChange
) -> SummaryCoverage:
    """Return how the files and hunks ``raw_document`` names differ from ``change``."""
    path_to_named_file = {
        named_file.path: named_file for named_file in _list_named_files(raw_document)
    }
    unnamed_parts: list[str] = []
    for file in change.files:
        named_file = path_to_named_file.get(file.path)
        if named_file is None:
            unnamed_parts.append(file.path)
            continue
        unnamed_parts.extend(
            _describe_hunk(file.path, hunk.header)
            for hunk in file.hunks
            if hunk.header not in named_file.headers
        )
    path_to_file = {file.path: file for file in change.files}
    stale_parts: list[str] = []
    for named_file in path_to_named_file.values():
        changed_file = path_to_file.get(named_file.path)
        if changed_file is None:
            stale_parts.append(named_file.path)
            continue
        stale_headers = named_file.headers - _list_headers(changed_file)
        stale_parts.extend(
            _describe_hunk(named_file.path, header)
            for header in sorted(stale_headers, key=_order)
        )
    return SummaryCoverage(tuple(unnamed_parts), tuple(stale_parts))


def _list_named_files(raw_document: JsonValue) -> list[NamedFile]:
    """Return each file the document lists by a path, with the headers it lists."""
    if not isinstance(raw_document, Mapping):
        return []
    named_files = []
    for raw_file in _list_objects(raw_document.get("files")):
        path = raw_file.get("path")
        if not isinstance(path, str):
            continue
        headers = set()
        for raw_hunk in _list_objects(raw_file.get("hunks")):
            header_text = raw_hunk.get("header")
            if not isinstance(header_text, str):
                continue
            try:
                headers.add(parse_hunk_header(header_text))
            except ValueError:
                continue
        named_files.append(NamedFile(path, frozenset(headers)))
    return named_files


def _list_objects(raw_value: JsonValue) -> list[Mapping[str, JsonValue]]:
    """Return the JSON objects in ``raw_value`` when it is a list; else none."""
    if not isinstance(raw_value, Sequence) or isinstance(raw_value, str):
        return []
    return [item for item in raw_value if isinstance(item, Mapping)]


def _list_headers(file: GitFileChange) -> frozenset[HunkHeader]:
    return frozenset(hunk.header for hunk in file.hunks)


def _order(header: HunkHeader) -> tuple[int, int]:
    return (header.old_start, header.new_start)


def _describe_hunk(path: str, header: HunkHeader) -> str:
    return f"{path} {header.format_text()}"
