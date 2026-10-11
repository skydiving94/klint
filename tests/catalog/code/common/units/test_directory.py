"""Directory units: their children and how a directory describes itself."""

from src.catalog.code.common.units.directory import AuditableDirectoryUnit
from src.catalog.code.common.units.file_metadata import AuditableFileMetadataUnit
from src.catalog.code.python.units.package import AuditablePythonPackageUnit


def test_directory_children_are_its_files_then_its_subdirectories() -> None:
    file_unit = AuditableFileMetadataUnit(unit_id="pkg/a.py", file_name="a.py")
    subdirectory = AuditablePythonPackageUnit(unit_id="pkg/sub")
    directory = AuditablePythonPackageUnit(
        unit_id="pkg", files=[file_unit], subdirectories=[subdirectory]
    )

    assert list(directory.children()) == [file_unit, subdirectory]
    assert subdirectory.children() == []


def test_directory_unit_describes_itself_without_assuming_a_language() -> None:
    file_unit = AuditableFileMetadataUnit(
        unit_id="docs/intro.md", file_name="intro.md", line_count=3
    )
    directory = AuditableDirectoryUnit(
        unit_id="docs", directory_path="docs", files=[file_unit]
    )

    content = directory.get_content()

    assert "docs" in content
    assert "intro.md (lines=3)" in content
    assert "Package Public API" not in content


def test_python_package_is_a_directory_unit_of_the_same_type() -> None:
    package = AuditablePythonPackageUnit(unit_id="d")

    assert isinstance(package, AuditableDirectoryUnit)
    assert package.unit_type == AuditableDirectoryUnit.unit_type
