"""Project extraction: one composite unit for a directory tree."""

import asyncio

import pytest

from klint.catalog.code.language_neutral.units.directory import ProjectDirectoryContext
from klint.core.models.location import Location
from tests.support.builders import (
    build_project_extractor,
    build_target_scanner,
    extract_python_project,
)
from tests.support.paths import MOCK_PROJECT


@pytest.mark.usefixtures("in_repo_root")
def test_project_extractor_builds_one_root_unit() -> None:
    unit = extract_python_project(MOCK_PROJECT)

    assert unit.unit_type == "project_directory"
    assert unit.unit_id == str(MOCK_PROJECT)
    assert unit.get_location() == Location(source=str(MOCK_PROJECT))
    assert unit.get_context() == ProjectDirectoryContext(
        file_names=[], subdirectory_names=["api", "domain", "utils"]
    )


@pytest.mark.usefixtures("in_repo_root")
def test_project_extractor_keeps_nothing_between_extractions() -> None:
    extractor = build_project_extractor()
    scanner = build_target_scanner()

    asyncio.run(extractor.extract(scanner.scan_directory(MOCK_PROJECT)))
    after_root = asyncio.run(
        extractor.extract(scanner.scan_directory(MOCK_PROJECT / "api"))
    )

    assert after_root == extract_python_project(MOCK_PROJECT / "api")
