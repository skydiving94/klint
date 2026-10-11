"""What reads each file and describes each directory of a project."""

import asyncio
from pathlib import Path

import pytest

from src.catalog.code.common.extractors.file_metadata_base import (
    BaseFileMetadataExtractor,
)
from src.catalog.code.common.extractors.language_neutral_directory_factory import (
    LanguageNeutralDirectoryUnitFactory,
)
from src.catalog.code.common.extractors.project import RecursiveProjectExtractor
from src.catalog.code.common.extractors.traits_based_extraction_delegator import (
    TraitsBasedExtractionDelegator,
)
from src.catalog.code.common.units.directory import AuditableDirectoryUnit
from src.catalog.code.common.units.file_metadata import AuditableFileMetadataUnit
from src.catalog.code.python.extractors.file_metadata import (
    PythonFileMetadataExtractor,
)
from src.catalog.code.python.extractors.package_factory import (
    PythonPackageUnitFactory,
)
from src.catalog.code.python.units.package import AuditablePythonPackageUnit
from src.core.models.file_traits import FileTraits
from tests.support.builders import (
    build_file_traits_identifier,
    extract_project,
    write_text,
)


class JavaMarkingExtractor(BaseFileMetadataExtractor):
    """Stands in for an extractor of another language; marks what it reads."""

    def extract_file(self, path: Path, traits: FileTraits) -> AuditableFileMetadataUnit:
        return AuditableFileMetadataUnit(
            unit_id=str(path),
            language=traits.language,
            file_name=path.name,
            file_path=str(path),
            classes=["read as java"],
        )


def _extract(
    delegator: TraitsBasedExtractionDelegator, target: Path
) -> AuditableDirectoryUnit:
    (unit,) = asyncio.run(RecursiveProjectExtractor(delegator).extract(target))
    assert isinstance(unit, AuditableDirectoryUnit)
    return unit


def test_each_file_is_read_by_the_extractor_for_its_language(tmp_path: Path) -> None:
    for name in ("a.py", "b.java", "c.txt"):
        write_text(tmp_path / "pkg" / name, "import os\n")

    files = extract_project(tmp_path / "pkg").files

    # All three hold the same text; only the Python file is read as Python.
    assert [(f.file_name, f.language, f.imports) for f in files] == [
        ("a.py", "python", ["os"]),
        ("b.java", "java", []),
        ("c.txt", None, []),
    ]


def test_extractor_registered_for_a_language_reads_that_languages_files(
    tmp_path: Path,
) -> None:
    for name in ("a.py", "b.java"):
        write_text(tmp_path / "pkg" / name, "import os\n")
    delegator = TraitsBasedExtractionDelegator(
        file_traits_identifier=build_file_traits_identifier(),
        language_to_file_metadata_extractor={
            "python": PythonFileMetadataExtractor(),
            "java": JavaMarkingExtractor(),
        },
        language_to_directory_unit_factory={},
    )

    files = _extract(delegator, tmp_path / "pkg").files

    assert [(f.file_name, f.imports, f.classes) for f in files] == [
        ("a.py", ["os"], []),
        ("b.java", [], ["read as java"]),
    ]


def test_directory_holding_no_python_is_not_described_as_a_python_package(
    tmp_path: Path,
) -> None:
    write_text(tmp_path / "docs" / "view.tsx", "export {};\n")
    write_text(tmp_path / "docs" / "guide" / "intro.md", "# Intro\n")

    root = extract_project(tmp_path / "docs")
    (guide,) = root.subdirectories

    for unit in (root, guide):
        assert not isinstance(unit, AuditablePythonPackageUnit)
        assert unit.unit_type == "project_directory"
        assert unit.language is None
        assert "Package Public API" not in unit.get_content()
    assert "intro.md" in guide.get_content()


def test_only_directories_holding_python_are_described_as_python_packages(
    tmp_path: Path,
) -> None:
    write_text(tmp_path / "repo" / "app" / "main.py", "x = 1\n")
    write_text(tmp_path / "repo" / "docs" / "intro.md", "# Intro\n")

    root = extract_project(tmp_path / "repo")
    app, docs = root.subdirectories

    # The root holds Python further down, so it is a package too.
    assert isinstance(root, AuditablePythonPackageUnit)
    assert isinstance(app, AuditablePythonPackageUnit)
    assert (root.language, app.language) == ("python", "python")
    assert not isinstance(docs, AuditablePythonPackageUnit)
    assert docs.language is None


@pytest.mark.parametrize(
    ("file_names", "language"),
    [
        (["a.py", "b.java", "c.java"], "java"),
        (["a.py", "b.py", "c.java"], "python"),
        (["a.py", "b.java"], "java"),  # a tie goes to the name that sorts first
        (["notes.txt", "view.tsx"], None),
    ],
)
def test_directory_is_described_in_the_language_most_files_beneath_it_are_in(
    tmp_path: Path, file_names: list[str], language: str | None
) -> None:
    for name in file_names:
        write_text(tmp_path / "pkg" / "sub" / name, "x\n")
    delegator = TraitsBasedExtractionDelegator(
        file_traits_identifier=build_file_traits_identifier(),
        language_to_file_metadata_extractor={},
        language_to_directory_unit_factory={
            "python": PythonPackageUnitFactory(),
            "java": LanguageNeutralDirectoryUnitFactory(),
        },
    )

    root = _extract(delegator, tmp_path / "pkg")
    (sub,) = root.subdirectories

    assert (root.language, sub.language) == (language, language)
