"""The unit types the built-in suites add to a registry."""

from tests.support.builders import UNIT_REGISTRY, build_unit_registry


def test_built_in_suites_register_their_unit_types() -> None:
    assert build_unit_registry().known_unit_types() == [
        "file",
        "file_metadata",
        "project_directory",
    ]


def test_builtin_unit_types_are_registered() -> None:
    known = set(UNIT_REGISTRY.known_unit_types())
    assert {"file", "file_metadata", "project_directory"} <= known
