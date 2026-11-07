"""Finding and replacing one summary of a change-summary document by its JSON pointer.

A pointer is written as a finding's location gives it: "#" and then the
JSON pointer of the summary, such as "#/files/0/hunks/2/summary".
"""

import copy
from collections.abc import Mapping, Sequence

from klint.core.models.reports import JsonValue

# The key a summary is held under, at every level of the document.
_SUMMARY_KEY = "summary"
_POINTER_START = "#/"


def find_summary(document: JsonValue, pointer: str) -> str:
    """Return the summary ``pointer`` names in ``document``.

    Raises ValueError when the pointer is not written as "#/...", names
    nothing in the document, or names something other than a summary text.
    """
    *parent_keys, last_key = _split_pointer(pointer)
    if last_key != _SUMMARY_KEY:
        raise ValueError(f"{pointer} does not end with /{_SUMMARY_KEY}")
    parent = _follow_keys(document, parent_keys, pointer)
    summary = parent.get(_SUMMARY_KEY) if isinstance(parent, Mapping) else None
    if not isinstance(summary, str):
        raise ValueError(f"{pointer} names no summary text")
    return summary


def replace_summary(document: JsonValue, pointer: str, summary: str) -> JsonValue:
    """Return a copy of ``document`` with ``summary`` at ``pointer``.

    Raises ValueError as find_summary does.
    """
    find_summary(document, pointer)
    replaced = copy.deepcopy(document)
    *parent_keys, _ = _split_pointer(pointer)
    parent = _follow_keys(replaced, parent_keys, pointer)
    if not isinstance(parent, dict):
        raise ValueError(f"{pointer} names no summary text")
    parent[_SUMMARY_KEY] = summary
    return replaced


def _split_pointer(pointer: str) -> list[str]:
    """Return the keys of ``pointer``, unescaped as RFC 6901 says."""
    if not pointer.startswith(_POINTER_START):
        raise ValueError(f"{pointer!r} is not a pointer of the form '#/...'")
    return [
        key.replace("~1", "/").replace("~0", "~")
        for key in pointer.removeprefix(_POINTER_START).split("/")
    ]


def _follow_keys(document: JsonValue, keys: Sequence[str], pointer: str) -> JsonValue:
    """Return what ``keys`` lead to from ``document``; raise ValueError if nothing."""
    value = document
    for key in keys:
        if isinstance(value, Mapping) and key in value:
            value = value[key]
        elif (
            isinstance(value, Sequence)
            and not isinstance(value, str)
            and key.isdigit()
            and int(key) < len(value)
        ):
            value = value[int(key)]
        else:
            raise ValueError(f"{pointer} names nothing in the document")
    return value
