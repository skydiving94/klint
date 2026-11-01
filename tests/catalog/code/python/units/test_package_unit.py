"""How a Python package is described to the judge."""

import pytest

from klint.catalog.code import PROJECT_STRUCTURE_KIND_ID
from tests.support.builders import list_judge_subjects
from tests.support.paths import MOCK_PROJECT, SnapshotAsserter


@pytest.mark.usefixtures("in_repo_root")
def test_project_directory_text_matches_snapshot(
    assert_snapshot: SnapshotAsserter,
) -> None:
    subjects = list_judge_subjects(MOCK_PROJECT, PROJECT_STRUCTURE_KIND_ID)

    (root_subject,) = [
        subject
        for subject in subjects
        if subject.startswith(f"Target Directory Under Audit: {MOCK_PROJECT} (")
    ]
    assert_snapshot("project_directory_root.txt", root_subject)
