"""Python package units built for a whole tree."""

from pathlib import Path

import pytest

from src.catalog.code.python.units.package import AuditablePythonPackageUnit
from tests.support.builders import extract_python_project, write_text
from tests.support.paths import MOCK_PROJECT, SnapshotAsserter


def _subdirectory(
    unit: AuditablePythonPackageUnit, name: str
) -> AuditablePythonPackageUnit:
    (match,) = [d for d in unit.subdirectories if d.directory_name == name]
    assert isinstance(match, AuditablePythonPackageUnit)
    return match


def test_python_factory_gives_every_package_the_same_module_names(
    tmp_path: Path,
) -> None:
    write_text(tmp_path / "app" / "api" / "routes.py", "from domain import models\n")
    write_text(tmp_path / "app" / "domain" / "models.py", "x = 1\n")

    root = extract_python_project(tmp_path / "app")
    api, domain = root.subdirectories

    assert isinstance(api, AuditablePythonPackageUnit)
    assert isinstance(domain, AuditablePythonPackageUnit)
    assert {"app", "api", "domain", "routes", "models"} <= set(
        root.project_module_names
    )
    assert api.project_module_names == root.project_module_names
    assert domain.project_module_names == root.project_module_names


@pytest.mark.usefixtures("in_repo_root")
def test_subdirectory_text_uses_module_names_from_the_whole_tree(
    assert_snapshot: SnapshotAsserter,
) -> None:
    inside_tree = _subdirectory(extract_python_project(MOCK_PROJECT), "api")
    alone = extract_python_project(MOCK_PROJECT / "api")

    assert_snapshot("project_directory_api.txt", inside_tree.get_content())
    assert "domain" in inside_tree.project_module_names
    assert "domain" not in alone.project_module_names
