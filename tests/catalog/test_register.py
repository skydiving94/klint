"""The unit types the built-in suites add to a registry."""

from tests.support.builders import build_unit_registry


def test_built_in_suites_register_their_unit_types() -> None:
    assert build_unit_registry().known_unit_types() == [
        "file",
        "file_metadata",
        "project_directory",
    ]
