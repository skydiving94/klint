"""How a Python package is described to the judge."""

import pytest

from tests.support.builders import extract_python_project
from tests.support.paths import MOCK_PROJECT, SnapshotAsserter


@pytest.mark.usefixtures("in_repo_root")
def test_project_directory_text_matches_snapshot(
    assert_snapshot: SnapshotAsserter,
) -> None:
    unit = extract_python_project(MOCK_PROJECT)
    assert_snapshot("project_directory_root.txt", unit.get_content())
