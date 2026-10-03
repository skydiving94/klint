"""Project extraction: one composite unit for a directory tree."""

import asyncio
from pathlib import Path

import pytest

from src.catalog.code.common.extractors.fallback_file_metadata import (
    FallbackFileMetadataExtractor,
)
from src.catalog.code.common.extractors.project import RecursiveProjectExtractor
from src.catalog.code.common.units.directory import AuditableDirectoryUnit
from src.catalog.code.python.extractors.file_metadata import (
    PythonFileMetadataExtractor,
)
from src.catalog.code.python.extractors.package_factory import (
    PythonPackageUnitFactory,
)
from tests.support.builders import (
    extract_python_project,
    python_project_extractor,
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
    extractor = python_project_extractor()

    asyncio.run(extractor.extract(MOCK_PROJECT))
    (after_root,) = asyncio.run(extractor.extract(MOCK_PROJECT / "api"))

    assert after_root == extract_python_project(MOCK_PROJECT / "api")


def test_project_extractor_uses_the_first_file_extractor_that_supports_a_file(
    tmp_path: Path,
) -> None:
    write_text(tmp_path / "pkg" / "a.py", "import os\n")
    write_text(tmp_path / "pkg" / "b.ts", "import fs from 'fs';\n")
    write_text(tmp_path / "pkg" / "c.txt", "import os\n")
    fallback_first = RecursiveProjectExtractor(
        file_extractors=[
            FallbackFileMetadataExtractor(),
            PythonFileMetadataExtractor(),
        ],
        directory_factory=PythonPackageUnitFactory(),
    )

    python_first = extract_python_project(tmp_path / "pkg")
    (shadowed,) = asyncio.run(fallback_first.extract(tmp_path / "pkg"))

    # Only a.py is read as Python; c.txt holds the same text but is not.
    assert [f.imports for f in python_first.files] == [["os"], [], []]
    assert isinstance(shadowed, AuditableDirectoryUnit)
    assert [f.imports for f in shadowed.files] == [[], [], []]
