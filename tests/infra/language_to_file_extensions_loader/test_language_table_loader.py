"""Reading which file extensions belong to which language."""

import json
from pathlib import Path

import pytest

from klint.infra.language_to_file_extensions_loader.language_table_loader import (
    load_file_extension_to_language,
)
from tests.support.builders import write_json, write_text
from tests.support.paths import DEFAULT_LANGUAGE_TO_FILE_EXTENSIONS


def test_built_in_file_gives_each_extension_its_language() -> None:
    assert load_file_extension_to_language(DEFAULT_LANGUAGE_TO_FILE_EXTENSIONS) == {
        ".py": "python",
        ".ts": "typescript",
        ".tsx": "typescript",
        ".js": "javascript",
        ".jsx": "javascript",
        ".mjs": "javascript",
        ".cjs": "javascript",
        ".java": "java",
        ".go": "go",
        ".c": "c",
        ".h": "c",
        ".cpp": "cpp",
        ".cc": "cpp",
        ".cxx": "cpp",
        ".hpp": "cpp",
        ".hh": "cpp",
        ".hxx": "cpp",
    }


def test_extensions_are_returned_in_lower_case(tmp_path: Path) -> None:
    path = write_json(tmp_path / "extensions.json", {"r": [".R", ".Rmd"]})

    assert load_file_extension_to_language(path) == {".r": "r", ".rmd": "r"}


def test_missing_file_is_reported_by_name(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match=r"does not exist: .*extensions\.json"):
        load_file_extension_to_language(tmp_path / "extensions.json")


def test_invalid_json_stops_with_an_error_naming_the_file(tmp_path: Path) -> None:
    path = write_text(tmp_path / "extensions.json", "{not json")

    with pytest.raises(ValueError, match=r"extensions\.json' is not valid JSON"):
        load_file_extension_to_language(path)


@pytest.mark.parametrize("content", [[], "python", 3, None])
def test_content_that_is_not_an_object_is_rejected(
    tmp_path: Path, content: object
) -> None:
    path = write_text(tmp_path / "extensions.json", json.dumps(content))

    with pytest.raises(ValueError, match=r"extensions\.json' must be an object"):
        load_file_extension_to_language(path)


@pytest.mark.parametrize(
    "extensions", [".py", [".py", 3], ["py"], ["."], {".py": True}, None]
)
def test_malformed_extensions_are_rejected(tmp_path: Path, extensions: object) -> None:
    path = write_text(tmp_path / "extensions.json", json.dumps({"python": extensions}))

    with pytest.raises(ValueError, match="invalid extensions for 'python'"):
        load_file_extension_to_language(path)


def test_extension_listed_under_two_languages_is_rejected(tmp_path: Path) -> None:
    path = write_json(tmp_path / "extensions.json", {"c": [".h"], "cpp": [".H"]})

    with pytest.raises(ValueError, match=r"'\.h' under both 'c' and 'cpp'"):
        load_file_extension_to_language(path)
