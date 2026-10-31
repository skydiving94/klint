"""Directory units: their children and how a directory describes itself."""

from pathlib import Path

from klint.catalog.code import PROJECT_STRUCTURE_KIND_ID
from klint.catalog.code.common.units.file_metadata import AuditableFileMetadataUnit
from klint.catalog.code.python.units.package import AuditablePythonPackageUnit
from klint.core.models.question_type import QuestionType
from klint.core.models.rule import AuditRule
from klint.core.models.unit_traits import UnitTraits
from tests.support.builders import list_judge_subjects, write_text


def test_directory_children_are_its_files_then_its_subdirectories() -> None:
    file_unit = AuditableFileMetadataUnit(unit_id="pkg/a.py", file_name="a.py")
    subdirectory = AuditablePythonPackageUnit(unit_id="pkg/sub")
    directory = AuditablePythonPackageUnit(
        unit_id="pkg", files=[file_unit], subdirectories=[subdirectory]
    )

    assert list(directory.children()) == [file_unit, subdirectory]
    assert subdirectory.children() == []


def test_directory_is_described_without_assuming_a_language(tmp_path: Path) -> None:
    docs = tmp_path / "docs"
    write_text(docs / "intro.md", "# Intro\n\nHello.\n")

    (subject,) = list_judge_subjects(docs, PROJECT_STRUCTURE_KIND_ID)

    assert subject.splitlines() == [
        f"Target Directory Under Audit: {docs}",
        "Summary: 1 immediate files, 0 immediate subdirectories",
        f"Directory: {docs}",
        "  Files:",
        "    - intro.md (lines=3)",
    ]


def test_rule_for_directories_applies_to_a_python_package() -> None:
    package = AuditablePythonPackageUnit(
        unit_id="d", traits=UnitTraits(language="python")
    )
    rule = AuditRule("r", QuestionType.CHOICE, "?", ["project_directory"])

    assert package.unit_type == "project_directory"
    assert rule.is_applicable_to(package)
