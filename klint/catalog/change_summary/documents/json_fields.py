"""Reads the fields of a parsed change-summary document, naming the place of a fault.

A place in the document is named by a JSON pointer, written as a URI
fragment: "#/root_package/files/0/summary".
"""

import warnings
from collections.abc import Mapping, Sequence

from klint.core import KlintWarning
from klint.core.models.reports import JsonValue


def build_document_error(pointer: str, problem: str) -> ValueError:
    """Return the error for a fault at ``pointer`` in the document."""
    return ValueError(f"Change-summary document: {pointer} {problem}")


def read_object(
    raw_value: JsonValue, pointer: str, field_names: frozenset[str]
) -> Mapping[str, JsonValue]:
    """Return ``raw_value`` as an object; warn about fields not in ``field_names``."""
    if not isinstance(raw_value, Mapping):
        raise build_document_error(pointer, "must be a JSON object")
    unknown_field_names = sorted(set(raw_value) - field_names)
    if unknown_field_names:
        warnings.warn(
            f"Change-summary document: {pointer} has unknown fields "
            f"{unknown_field_names}, which are ignored; known fields: "
            f"{sorted(field_names)}",
            KlintWarning,
            stacklevel=3,
        )
    return raw_value


def read_field(
    raw_object: Mapping[str, JsonValue], field_name: str, pointer: str
) -> JsonValue:
    """Return the field. Raises ValueError when it is missing."""
    if field_name not in raw_object:
        raise build_document_error(f"{pointer}/{field_name}", "is missing")
    return raw_object[field_name]


def read_text(
    raw_object: Mapping[str, JsonValue], field_name: str, pointer: str
) -> str:
    """Return the field as text that is not blank."""
    return _check_text(read_field(raw_object, field_name, pointer), field_name, pointer)


def read_optional_text(
    raw_object: Mapping[str, JsonValue], field_name: str, pointer: str
) -> str | None:
    """Return the field as text that is not blank; None when it is absent or null."""
    raw_value = raw_object.get(field_name)
    if raw_value is None:
        return None
    return _check_text(raw_value, field_name, pointer)


def read_count(
    raw_object: Mapping[str, JsonValue], field_name: str, pointer: str
) -> int:
    """Return the field as a whole number of at least 0."""
    raw_value = read_field(raw_object, field_name, pointer)
    if isinstance(raw_value, bool) or not isinstance(raw_value, int) or raw_value < 0:
        raise build_document_error(
            f"{pointer}/{field_name}", "must be a whole number of at least 0"
        )
    return raw_value


def list_items(
    raw_object: Mapping[str, JsonValue],
    field_name: str,
    pointer: str,
    *,
    is_optional: bool = False,
) -> list[tuple[JsonValue, str]]:
    """Return each item of the list in the field, with its pointer.

    An optional field that is absent or null holds no item.
    """
    if is_optional and raw_object.get(field_name) is None:
        return []
    raw_value = read_field(raw_object, field_name, pointer)
    if not isinstance(raw_value, Sequence) or isinstance(raw_value, str):
        raise build_document_error(f"{pointer}/{field_name}", "must be a list")
    return [
        (item, f"{pointer}/{field_name}/{index}")
        for index, item in enumerate(raw_value)
    ]


def _check_text(raw_value: JsonValue, field_name: str, pointer: str) -> str:
    if not isinstance(raw_value, str) or not raw_value.strip():
        raise build_document_error(
            f"{pointer}/{field_name}", "must be text that is not blank"
        )
    return raw_value
