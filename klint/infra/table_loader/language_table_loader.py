"""Reads which file extensions belong to which language from a JSON file."""

from pathlib import Path

from klint.infra.table_loader.json_object_file import read_json_object_file


def load_file_extension_to_language(path: Path) -> dict[str, str]:
    """Return the language of each file extension listed in ``path``.

    The file is an object that maps each language name to the list of file
    extensions written in it. The result maps each extension, in lower case,
    to its language. Raises FileNotFoundError when the file is missing, and
    ValueError naming the file when its content is not valid.
    """
    raw = read_json_object_file(
        path,
        "Language-to-file-extensions file",
        "an object that maps each language to its extensions",
    )
    file_extension_to_language: dict[str, str] = {}
    for raw_language, raw_extensions in raw.items():
        language = str(raw_language)
        for extension in _validate_extensions(raw_extensions, language, path):
            listed_under = file_extension_to_language.setdefault(extension, language)
            if listed_under != language:
                raise ValueError(
                    f"Language-to-file-extensions file '{path}' lists extension "
                    f"'{extension}' under both '{listed_under}' and '{language}'"
                )
    return file_extension_to_language


def _validate_extensions(
    raw_extensions: object, language: str, path: Path
) -> list[str]:
    """Return the extensions in lower case; raise if any is not like '.py'."""
    if not isinstance(raw_extensions, list) or not all(
        isinstance(item, str) and item.startswith(".") and len(item) > 1
        for item in raw_extensions
    ):
        raise ValueError(
            f"Language-to-file-extensions file '{path}' has invalid extensions for "
            f"'{language}': {raw_extensions!r}; expected a list of strings "
            "such as '.py'"
        )
    return [extension.lower() for extension in raw_extensions]
