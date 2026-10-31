"""Reading the tag detection tables from a JSON file."""

from pathlib import Path
from typing import Any

import pytest

from klint.infra.tag_detection_loader.json_loader import load_tag_detection_table
from tests.support.builders import write_json
from tests.support.paths import TAG_DETECTION


def test_tables_are_read_with_extensions_and_tags_in_lower_case(
    tmp_path: Path,
) -> None:
    path = write_json(
        tmp_path / "tags.json",
        {
            "extension_to_tags": {".TSX": ["Frontend"]},
            "path_glob_to_tags": {"**/api/**": ["backend", "api"]},
        },
    )

    table = load_tag_detection_table(path)

    assert table.extension_to_tags == {".tsx": frozenset({"frontend"})}
    assert table.path_glob_to_tags == {"**/api/**": frozenset({"backend", "api"})}


def test_table_left_out_is_empty(tmp_path: Path) -> None:
    table = load_tag_detection_table(write_json(tmp_path / "tags.json", {}))

    assert (table.extension_to_tags, table.path_glob_to_tags) == ({}, {})


@pytest.mark.parametrize(
    ("content", "message"),
    [
        ({"extension_to_tag": {}}, "unknown tables"),
        ({"extension_to_tags": []}, "invalid extension_to_tags"),
        ({"extension_to_tags": {"tsx": ["frontend"]}}, "invalid extension 'tsx'"),
        ({"path_glob_to_tags": {"**/api/**": []}}, "invalid tags for '\\*\\*/api"),
        ({"path_glob_to_tags": {"**/api/**": "backend"}}, "invalid tags"),
    ],
)
def test_invalid_table_stops_with_an_error_naming_the_file(
    tmp_path: Path, content: dict[str, Any], message: str
) -> None:
    path = write_json(tmp_path / "tags.json", content)

    with pytest.raises(ValueError, match=message) as error:
        load_tag_detection_table(path)
    assert str(path) in str(error.value)


def test_missing_file_is_reported(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        load_tag_detection_table(tmp_path / "absent.json")


def test_built_in_tables_tag_both_sides() -> None:
    table = load_tag_detection_table(TAG_DETECTION)

    assert table.extension_to_tags[".tsx"] == frozenset({"frontend"})
    assert table.path_glob_to_tags["**/api/**"] == frozenset({"backend"})
