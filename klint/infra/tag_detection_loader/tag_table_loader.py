"""Reads the tag detection tables of a suite from a JSON file."""

import json
from pathlib import Path

from klint.core.models.tag_detection_table import TagDetectionTable

_TABLE_NAMES = frozenset({"extension_to_tags", "path_glob_to_tags", "import_to_tags"})


def load_tag_detection_table(path: Path) -> TagDetectionTable:
    """Return the tag detection tables in ``path``.

    The file is an object holding "extension_to_tags", "path_glob_to_tags"
    and "import_to_tags", each an object that maps a signal to a list of
    tags; any may be left out. Extensions and tags are kept in lower
    case. Raises FileNotFoundError when the file is missing, and ValueError
    naming the file when its content is not valid.
    """
    if not path.is_file():
        raise FileNotFoundError(f"Tag detection file does not exist: {path}")
    try:
        raw: object = json.loads(path.read_text(encoding="utf-8"))
    except ValueError as error:
        raise ValueError(
            f"Tag detection file '{path}' is not valid JSON: {error}"
        ) from error
    if not isinstance(raw, dict):
        raise ValueError(f"Tag detection file '{path}' must be a JSON object")
    unknown_names = sorted(str(name) for name in set(raw) - _TABLE_NAMES)
    if unknown_names:
        raise ValueError(
            f"Tag detection file '{path}' has unknown tables {unknown_names}; "
            f"known tables: {sorted(_TABLE_NAMES)}"
        )
    extension_to_tags = _read_signal_to_tags(raw, "extension_to_tags", path)
    for extension in extension_to_tags:
        if not extension.startswith(".") or len(extension) < 2:
            raise ValueError(
                f"Tag detection file '{path}' has an invalid extension "
                f"'{extension}' in extension_to_tags; expected one such as '.tsx'"
            )
    return TagDetectionTable(
        extension_to_tags={
            extension.lower(): tags for extension, tags in extension_to_tags.items()
        },
        path_glob_to_tags=_read_signal_to_tags(raw, "path_glob_to_tags", path),
        import_to_tags=_read_signal_to_tags(raw, "import_to_tags", path),
    )


def _read_signal_to_tags(
    raw: dict[object, object], table_name: str, path: Path
) -> dict[str, frozenset[str]]:
    """Return the table ``table_name``; empty when the file leaves it out."""
    raw_table = raw.get(table_name, {})
    if not isinstance(raw_table, dict):
        raise ValueError(
            f"Tag detection file '{path}' has an invalid {table_name}; expected an "
            "object that maps each signal to a list of tags"
        )
    signal_to_tags: dict[str, frozenset[str]] = {}
    for signal, raw_tags in raw_table.items():
        if (
            not isinstance(raw_tags, list)
            or not raw_tags
            or not all(isinstance(tag, str) and tag for tag in raw_tags)
        ):
            raise ValueError(
                f"Tag detection file '{path}' has invalid tags for '{signal}' in "
                f"{table_name}: {raw_tags!r}; expected a non-empty list of strings"
            )
        signal_to_tags[str(signal)] = frozenset(tag.lower() for tag in raw_tags)
    return signal_to_tags
