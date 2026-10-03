"""Directory units: their children and what the generic base leaves open."""

import pytest

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


def test_generic_directory_unit_cannot_be_built_on_its_own() -> None:
    assert isinstance(AuditablePythonPackageUnit(unit_id="d"), AuditableDirectoryUnit)
    with pytest.raises(TypeError, match="abstract"):
        AuditableDirectoryUnit(unit_id="d")  # type: ignore[abstract]
