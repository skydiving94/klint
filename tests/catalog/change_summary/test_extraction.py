"""What the change-summary extractor reads from a document, and what it refuses."""

from collections.abc import Callable
from dataclasses import asdict

import pytest

from klint.core.klint_warning import KlintWarning
from klint.core.models.location import Location
from tests.support.change_summary import (
    APP_PACKAGE_POINTER,
    GREET_FILE_POINTER,
    GREETING_DOCUMENT,
    ChangeSummaryDocumentData,
    copy_greeting_document,
    extract_summary_units,
)

DocumentChange = Callable[[ChangeSummaryDocumentData], None]


def _find_greet_file(document: ChangeSummaryDocumentData) -> dict[str, object]:
    file: dict[str, object] = document["root_package"]["packages"][0]["files"][0]
    return file


def _find_greeting_hunk(document: ChangeSummaryDocumentData) -> dict[str, object]:
    hunks = _find_greet_file(document)["hunks"]
    assert isinstance(hunks, list)
    hunk: dict[str, object] = hunks[0]
    return hunk


def test_each_summary_is_a_unit_that_comes_before_those_nested_in_it() -> None:
    units = extract_summary_units(GREETING_DOCUMENT)

    assert [(unit.unit_id, unit.unit_type) for unit in units] == [
        ("./", "package_summary"),
        ("app/", "package_summary"),
        ("app/greet.py", "file_summary"),
        ("app/greet.py#1", "hunk_summary"),
        ("app/greet.py#2", "hunk_summary"),
        ("README.md", "file_summary"),
        ("README.md#1", "hunk_summary"),
    ]
    unit_id_to_child_ids = {
        unit.unit_id: [child.unit_id for child in unit.children()] for unit in units
    }
    assert unit_id_to_child_ids["./"] == ["app/", "README.md"]
    assert unit_id_to_child_ids["app/greet.py"] == ["app/greet.py#1", "app/greet.py#2"]


def test_a_unit_points_at_its_summary_and_a_hunk_also_at_its_code() -> None:
    unit_id_to_unit = {
        unit.unit_id: unit for unit in extract_summary_units(GREETING_DOCUMENT)
    }

    assert unit_id_to_unit["./"].get_location() == Location("#/root_package/summary")
    assert unit_id_to_unit["app/greet.py"].get_location() == Location(
        f"{GREET_FILE_POINTER}/summary"
    )
    assert unit_id_to_unit["app/greet.py#1"].get_location() == Location(
        f"{GREET_FILE_POINTER}/hunks/0/summary"
    )
    # The lines a hunk adds; for a hunk that only removes, the lines removed.
    assert unit_id_to_unit["app/greet.py#1"].get_evidence_location() == Location(
        "app/greet.py", 3, 4
    )
    assert unit_id_to_unit["app/greet.py#2"].get_evidence_location() == Location(
        "app/greet.py", 1, 1
    )
    assert unit_id_to_unit["README.md"].get_evidence_location() is None


def test_lines_only_removed_from_a_renamed_file_sit_at_its_old_path() -> None:
    document = copy_greeting_document()
    greet_file = _find_greet_file(document)
    greet_file.update(
        path="app/greeting.py", old_path="app/greet.py", change_kind="renamed"
    )
    hunks = greet_file["hunks"]
    assert isinstance(hunks, list)
    hunks[1]["hunk_id"] = "app/greeting.py#2"

    (removal,) = [
        unit
        for unit in extract_summary_units(document)
        if unit.unit_id == "app/greeting.py#2"
    ]

    assert removal.get_evidence_location() == Location("app/greet.py", 1, 1)


def test_context_names_the_level_the_path_and_the_summary() -> None:
    unit_id_to_context = {
        unit.unit_id: asdict(unit.get_context())
        for unit in extract_summary_units(GREETING_DOCUMENT)
    }

    assert unit_id_to_context["./"] == {
        "level": "commit",
        "path": ".",
        "summary": "Greets people by their stripped name, and adds a README.",
    }
    assert unit_id_to_context["app/"]["level"] == "package"
    assert unit_id_to_context["README.md"]["level"] == "file"
    assert unit_id_to_context["README.md#1"] == {
        "level": "hunk",
        "path": "README.md",
        "summary": "Adds a title and a one-line description of the greeter.",
    }


def test_a_package_path_may_end_with_a_slash() -> None:
    document = copy_greeting_document()
    document["root_package"]["packages"][0]["path"] = "app/"

    unit_ids = [unit.unit_id for unit in extract_summary_units(document)]

    assert unit_ids[:3] == ["./", "app/", "app/greet.py"]


def _set_schema_version(document: ChangeSummaryDocumentData) -> None:
    document["schema_version"] = 2


def _set_root_path(document: ChangeSummaryDocumentData) -> None:
    document["root_package"]["path"] = "src"


def _drop_hunk_summary(document: ChangeSummaryDocumentData) -> None:
    del _find_greeting_hunk(document)["summary"]


def _blank_file_summary(document: ChangeSummaryDocumentData) -> None:
    _find_greet_file(document)["summary"] = "  "


def _set_unknown_change_kind(document: ChangeSummaryDocumentData) -> None:
    _find_greet_file(document)["change_kind"] = "edited"


def _give_modified_file_an_old_path(document: ChangeSummaryDocumentData) -> None:
    _find_greet_file(document)["old_path"] = "app/old_greet.py"


def _rename_without_old_path(document: ChangeSummaryDocumentData) -> None:
    _find_greet_file(document)["change_kind"] = "renamed"


def _add_line_beyond_the_count(document: ChangeSummaryDocumentData) -> None:
    _find_greeting_hunk(document)["removed_lines"] = ["a", "b"]


def _set_negative_line_count(document: ChangeSummaryDocumentData) -> None:
    _find_greeting_hunk(document)["new_start"] = -1


def _empty_the_hunk(document: ChangeSummaryDocumentData) -> None:
    _find_greeting_hunk(document).update(
        old_line_count=0, new_line_count=0, removed_lines=[], added_lines=[]
    )


def _move_file_out_of_its_package(document: ChangeSummaryDocumentData) -> None:
    _find_greet_file(document)["path"] = "lib/greet.py"


def _repeat_a_hunk_id(document: ChangeSummaryDocumentData) -> None:
    hunks = _find_greet_file(document)["hunks"]
    assert isinstance(hunks, list)
    hunks[1]["hunk_id"] = "app/greet.py#1"


def _make_files_text(document: ChangeSummaryDocumentData) -> None:
    document["root_package"]["files"] = "README.md"


@pytest.mark.parametrize(
    ("change_document", "message"),
    [
        (_set_schema_version, "#/schema_version is 2; klint reads schema_version 1"),
        (_set_root_path, "#/root_package/path is 'src'; the root package is '.'"),
        (_drop_hunk_summary, f"{GREET_FILE_POINTER}/hunks/0/summary is missing"),
        (_blank_file_summary, f"{GREET_FILE_POINTER}/summary must be text"),
        (_set_unknown_change_kind, "change_kind is 'edited'; known kinds: ['added'"),
        (_give_modified_file_an_old_path, "only a renamed file has one"),
        (_rename_without_old_path, "old_path must be the path before the rename"),
        (_add_line_beyond_the_count, "holds 2 lines, but the hunk's line count is 1"),
        (_set_negative_line_count, "new_start must be a whole number of at least 0"),
        (_empty_the_hunk, f"{GREET_FILE_POINTER}/hunks/0 removes no line"),
        (
            _move_file_out_of_its_package,
            f"{GREET_FILE_POINTER}/path is 'lib/greet.py', which is not inside "
            "its package 'app'",
        ),
        (
            _repeat_a_hunk_id,
            f"{GREET_FILE_POINTER}/hunks/1/summary has the ID 'app/greet.py#1'",
        ),
        (_make_files_text, "#/root_package/files must be a list"),
    ],
)
def test_a_document_of_the_wrong_shape_is_refused_naming_the_place(
    change_document: DocumentChange, message: str
) -> None:
    document = copy_greeting_document()
    change_document(document)

    with pytest.raises(ValueError, match="Change-summary document: ") as error:
        extract_summary_units(document)

    assert message in str(error.value)


def test_content_that_is_not_an_object_is_refused() -> None:
    with pytest.raises(ValueError, match="Change-summary document: # must be a JSON"):
        extract_summary_units(["not", "a", "document"])


def test_an_unknown_field_is_ignored_with_a_warning() -> None:
    document = copy_greeting_document()
    document["root_package"]["packages"][0]["summery"] = "A typo."

    with pytest.warns(KlintWarning, match=r"unknown fields \['summery'\]") as record:
        units = extract_summary_units(document)

    assert APP_PACKAGE_POINTER in str(record[0].message)
    assert len(units) == len(extract_summary_units(GREETING_DOCUMENT))


def test_packages_nested_too_deeply_to_read_are_refused() -> None:
    document = copy_greeting_document()
    package = document["root_package"]
    path = "d"
    for _ in range(3_000):
        nested = {
            "path": path,
            "summary": "A level.",
            "packages": [],
            "files": [],
        }
        package["packages"] = [nested]
        package = nested
        path = f"{path}/d"

    with pytest.raises(ValueError, match="nested too deeply to read"):
        extract_summary_units(document)
