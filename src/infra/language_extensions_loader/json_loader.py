"""Reads which file extensions belong to which language from a JSON file."""

import json
from pathlib import Path


def load_language_extensions(path: Path) -> dict[str, str]:
    """Return the language of each file extension listed in ``path``.

    The file is an object that maps each language name to the list of file
    extensions written in it. The result maps each extension, in lower case,
    to its language. Raises FileNotFoundError when the file is missing, and
    ValueError naming the file when its content is not valid.
    """
    if not path.is_file():
        raise FileNotFoundError(f"Language extensions file does not exist: {path}")
    try:
        raw: object = json.loads(path.read_text(encoding="utf-8"))
    except ValueError as error:
        raise ValueError(
            f"Language extensions file '{path}' is not valid JSON: {error}"
        ) from error
    if not isinstance(raw, dict):
        raise ValueError(
            f"Language extensions file '{path}' must be an object that maps "
            "each language to its extensions"
        )

    language_by_extension: dict[str, str] = {}
    for language, raw_extensions in raw.items():
        for extension in _validate_extensions(raw_extensions, language, path):
            listed_under = language_by_extension.setdefault(extension, language)
            if listed_under != language:
                raise ValueError(
                    f"Language extensions file '{path}' lists extension "
                    f"'{extension}' under both '{listed_under}' and '{language}'"
                )
    return language_by_extension


def _validate_extensions(
    raw_extensions: object, language: str, path: Path
) -> list[str]:
    """Return the extensions in lower case; raise if any is not like '.py'."""
    if not isinstance(raw_extensions, list) or not all(
        isinstance(item, str) and item.startswith(".") and len(item) > 1
        for item in raw_extensions
    ):
        raise ValueError(
            f"Language extensions file '{path}' has invalid extensions for "
            f"'{language}': {raw_extensions!r}; expected a list of strings "
            "such as '.py'"
        )
    return [extension.lower() for extension in raw_extensions]
