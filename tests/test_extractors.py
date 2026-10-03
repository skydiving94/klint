"""Unit extraction: whole files, Python file metadata and project trees."""

import asyncio
from pathlib import Path

import pytest

from src.catalog.code.common.extractors.directory_factory import (
    BaseDirectoryUnitFactory,
)
from src.catalog.code.common.extractors.fallback_file_metadata import (
    FallbackFileMetadataExtractor,
)
from src.catalog.code.common.extractors.project import RecursiveProjectExtractor
from src.catalog.code.common.units.directory import AuditableDirectoryUnit
from src.catalog.code.common.units.file_metadata import AuditableFileMetadataUnit
from src.catalog.code.python.extractors.file_metadata import (
    PythonFileMetadataExtractor,
)
from src.catalog.code.python.extractors.package_factory import (
    PythonPackageUnitFactory,
)
from src.catalog.code.python.units.package import AuditablePythonPackageUnit
from src.catalog.common.extractors.whole_file import WholeFileExtractor
from src.catalog.common.units.file import AuditableFileUnit
from tests.helpers import SnapshotAsserter

MOCK_PROJECT = Path("examples/mock_bad_project")

MODULE_SOURCE = """\
import os
import json as j
from pathlib import Path
from . import sibling
from .models import order
from pkg.sub import helper_fn, HelperClass

__all__ = ["run", "Public"]


class Public:
    def method(self):
        return None


def run():
    import sqlite3


async def arun():
    return None
"""


def _write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def _python_project_extractor() -> RecursiveProjectExtractor:
    return RecursiveProjectExtractor(
        file_extractors=[PythonFileMetadataExtractor()],
        directory_factory=PythonPackageUnitFactory(),
    )


def _extract_project(target: Path) -> AuditablePythonPackageUnit:
    (unit,) = asyncio.run(_python_project_extractor().extract(target))
    assert isinstance(unit, AuditablePythonPackageUnit)
    return unit


def _subdirectory(
    unit: AuditablePythonPackageUnit, name: str
) -> AuditablePythonPackageUnit:
    (match,) = [d for d in unit.subdirectories if d.directory_name == name]
    assert isinstance(match, AuditablePythonPackageUnit)
    return match


# --- whole file ------------------------------------------------------------


def test_whole_file_extractor_returns_one_unit_spanning_the_file(
    tmp_path: Path,
) -> None:
    target = _write(tmp_path / "a.py", "x = 1\ny = 2\nz = 3\n")

    (unit,) = asyncio.run(WholeFileExtractor().extract(target))

    assert isinstance(unit, AuditableFileUnit)
    assert unit.unit_type == "file"
    assert unit.unit_id == str(target)
    assert unit.get_content() == "x = 1\ny = 2\nz = 3\n"
    assert unit.get_metadata() == {"file_path": str(target), "line_range": [1, 3]}


# --- file metadata ---------------------------------------------------------


def test_python_metadata_lists_imports_exports_classes_and_functions(
    tmp_path: Path,
) -> None:
    target = _write(tmp_path / "module.py", MODULE_SOURCE)

    unit = PythonFileMetadataExtractor().extract_file(target)

    assert unit.unit_type == "file_metadata"
    assert unit.file_name == "module.py"
    assert unit.line_count == len(MODULE_SOURCE.splitlines())
    # Top-level imports in source order, then the one nested inside run().
    assert unit.imports == [
        "os",
        "json",
        "pathlib",
        ".",
        ".sibling",
        ".models",
        ".models.order",
        "pkg.sub",
        "pkg.sub.helper_fn",
        "sqlite3",
    ]
    assert unit.exports == ["Public", "run"]
    assert unit.classes == ["Public"]
    assert unit.functions == ["run", "arun"]


def test_init_file_exports_the_names_it_imports(tmp_path: Path) -> None:
    source = "from .a import Foo, bar as baz\n"
    init_unit = PythonFileMetadataExtractor().extract_file(
        _write(tmp_path / "__init__.py", source)
    )
    plain_unit = PythonFileMetadataExtractor().extract_file(
        _write(tmp_path / "plain.py", source)
    )
    assert init_unit.exports == ["Foo", "baz"]
    assert plain_unit.exports == []


def test_python_metadata_survives_a_syntax_error(tmp_path: Path) -> None:
    target = _write(tmp_path / "broken.py", "def (:\n    pass\n")

    unit = PythonFileMetadataExtractor().extract_file(target)

    assert unit.line_count == 2
    assert (unit.imports, unit.exports, unit.classes, unit.functions) == (
        [],
        [],
        [],
        [],
    )


def test_metadata_extractors_choose_files_by_suffix() -> None:
    python_extractor = PythonFileMetadataExtractor()
    assert python_extractor.supports(Path("a.py"))
    assert python_extractor.supports(Path("A.PY"))
    assert not python_extractor.supports(Path("a.ts"))
    assert FallbackFileMetadataExtractor().supports(Path("a.ts"))


def test_fallback_metadata_records_only_name_and_line_count(tmp_path: Path) -> None:
    target = _write(tmp_path / "view.tsx", "import React from 'react';\nexport {};\n")

    unit = FallbackFileMetadataExtractor().extract_file(target)

    assert unit.get_content() == "view.tsx (lines=2)"
    assert unit.imports == []


# --- project tree ----------------------------------------------------------


@pytest.mark.usefixtures("in_repo_root")
def test_project_extractor_builds_one_root_unit() -> None:
    unit = _extract_project(MOCK_PROJECT)

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
    _write(tmp_path / "pkg" / "kept.py", "x = 1\n")
    _write(tmp_path / "pkg" / "klint.json", "{}")
    _write(tmp_path / "pkg" / "logo.png", "not really an image")
    _write(tmp_path / "pkg" / "__pycache__" / "kept.cpython-312.pyc", "")
    _write(tmp_path / "pkg" / "node_modules" / "dep" / "index.js", "")

    unit = _extract_project(tmp_path / "pkg")

    assert [f.file_name for f in unit.files] == ["kept.py"]
    assert unit.subdirectories == []


@pytest.mark.usefixtures("in_repo_root")
def test_project_directory_text_matches_snapshot(
    assert_snapshot: SnapshotAsserter,
) -> None:
    unit = _extract_project(MOCK_PROJECT)
    assert_snapshot("project_directory_root.txt", unit.get_content())


@pytest.mark.usefixtures("in_repo_root")
def test_subdirectory_text_uses_module_names_from_the_whole_tree(
    assert_snapshot: SnapshotAsserter,
) -> None:
    inside_tree = _subdirectory(_extract_project(MOCK_PROJECT), "api")
    alone = _extract_project(MOCK_PROJECT / "api")

    assert_snapshot("project_directory_api.txt", inside_tree.get_content())
    assert "domain" in inside_tree.project_module_names
    assert "domain" not in alone.project_module_names


@pytest.mark.usefixtures("in_repo_root")
def test_project_extractor_keeps_nothing_between_extractions() -> None:
    extractor = _python_project_extractor()

    asyncio.run(extractor.extract(MOCK_PROJECT))
    (after_root,) = asyncio.run(extractor.extract(MOCK_PROJECT / "api"))

    assert after_root == _extract_project(MOCK_PROJECT / "api")


def test_project_extractor_uses_the_first_file_extractor_that_supports_a_file(
    tmp_path: Path,
) -> None:
    _write(tmp_path / "pkg" / "a.py", "import os\n")
    _write(tmp_path / "pkg" / "b.ts", "import fs from 'fs';\n")
    _write(tmp_path / "pkg" / "c.txt", "import os\n")
    fallback_first = RecursiveProjectExtractor(
        file_extractors=[
            FallbackFileMetadataExtractor(),
            PythonFileMetadataExtractor(),
        ],
        directory_factory=PythonPackageUnitFactory(),
    )

    python_first = _extract_project(tmp_path / "pkg")
    (shadowed,) = asyncio.run(fallback_first.extract(tmp_path / "pkg"))

    # Only a.py is read as Python; c.txt holds the same text but is not.
    assert [f.imports for f in python_first.files] == [["os"], [], []]
    assert isinstance(shadowed, AuditableDirectoryUnit)
    assert [f.imports for f in shadowed.files] == [[], [], []]


# --- directory factories ---------------------------------------------------


class PlainDirectoryUnit(AuditableDirectoryUnit):
    """A directory described by its name alone."""

    unit_type = "plain_directory"

    def get_content(self) -> str:
        return self.directory_name


class PlainDirectoryFactory(BaseDirectoryUnitFactory):
    def build(
        self,
        directory: Path,
        files: list[AuditableFileMetadataUnit],
        subdirectories: list[AuditableDirectoryUnit],
    ) -> AuditableDirectoryUnit:
        return PlainDirectoryUnit(
            unit_id=str(directory),
            directory_path=str(directory),
            files=files,
            subdirectories=subdirectories,
        )


def test_directory_factory_decides_the_unit_for_every_directory(
    tmp_path: Path,
) -> None:
    _write(tmp_path / "docs" / "guide" / "intro.md", "# Intro\n")
    extractor = RecursiveProjectExtractor(
        file_extractors=[], directory_factory=PlainDirectoryFactory()
    )

    (root,) = asyncio.run(extractor.extract(tmp_path / "docs"))

    assert isinstance(root, PlainDirectoryUnit)
    assert root.get_content() == "docs"
    (guide,) = root.subdirectories
    assert isinstance(guide, PlainDirectoryUnit)
    assert [f.file_name for f in guide.files] == ["intro.md"]


def test_python_factory_gives_every_package_the_same_module_names(
    tmp_path: Path,
) -> None:
    _write(tmp_path / "app" / "api" / "routes.py", "from domain import models\n")
    _write(tmp_path / "app" / "domain" / "models.py", "x = 1\n")

    root = _extract_project(tmp_path / "app")
    api, domain = root.subdirectories

    assert isinstance(api, AuditablePythonPackageUnit)
    assert isinstance(domain, AuditablePythonPackageUnit)
    assert {"app", "api", "domain", "routes", "models"} <= set(
        root.project_module_names
    )
    assert api.project_module_names == root.project_module_names
    assert domain.project_module_names == root.project_module_names
