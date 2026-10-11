"""Project extraction: one composite unit for a directory tree."""

import asyncio
from pathlib import Path

import pytest

from tests.support.builders import (
    build_project_extractor,
    extract_python_project,
    write_text,
)
from tests.support.paths import MOCK_PROJECT


@pytest.mark.usefixtures("in_repo_root")
def test_project_extractor_builds_one_root_unit() -> None:
    unit = extract_python_project(MOCK_PROJECT)

    assert unit.unit_type == "project_directory"
    assert unit.unit_id == str(MOCK_PROJECT)
    assert unit.get_metadata() == {
        "directory_path": str(MOCK_PROJECT),
        "file_names": [],
        "subdirectory_names": ["api", "domain", "utils"],
    }


def test_project_extractor_skips_ignored_files_and_directories(
    tmp_path: Path,
) -> None:
    write_text(tmp_path / "pkg" / "kept.py", "x = 1\n")
    write_text(tmp_path / "pkg" / "klint.json", "{}")
    write_text(tmp_path / "pkg" / "logo.png", "not really an image")
    write_text(tmp_path / "pkg" / "__pycache__" / "kept.cpython-312.pyc", "")
    write_text(tmp_path / "pkg" / "node_modules" / "dep" / "index.js", "")

    unit = extract_python_project(tmp_path / "pkg")

    assert [f.file_name for f in unit.files] == ["kept.py"]
    assert unit.subdirectories == []


@pytest.mark.usefixtures("in_repo_root")
def test_project_extractor_keeps_nothing_between_extractions() -> None:
    extractor = build_project_extractor()

    asyncio.run(extractor.extract(MOCK_PROJECT))
    (after_root,) = asyncio.run(extractor.extract(MOCK_PROJECT / "api"))

    assert after_root == extract_python_project(MOCK_PROJECT / "api")
