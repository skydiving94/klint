"""Properties every auditable unit shares."""

import dataclasses

import pytest

from src.catalog.code.common.units.file_metadata import AuditableFileMetadataUnit
from src.catalog.code.python.units.package import AuditablePythonPackageUnit
from src.catalog.common.units.file import AuditableFileUnit
from src.core.models.unit import AuditableUnit

UNIT_CLASSES: list[type[AuditableUnit]] = [
    AuditableFileUnit,
    AuditableFileMetadataUnit,
    AuditablePythonPackageUnit,
]


@pytest.mark.parametrize("unit_class", UNIT_CLASSES)
def test_unit_language_is_unknown_by_default(unit_class: type[AuditableUnit]) -> None:
    assert unit_class(unit_id="u").language is None


@pytest.mark.parametrize("unit_class", UNIT_CLASSES)
def test_unit_language_can_be_set(unit_class: type[AuditableUnit]) -> None:
    assert unit_class(unit_id="u", language="python").language == "python"


def test_unit_language_is_keyword_only() -> None:
    # A positional second argument is still the unit's own first field.
    unit = AuditableFileUnit("a.py", "x = 1")
    assert unit.get_content() == "x = 1"
    assert unit.language is None


def test_unit_language_survives_a_copy_and_is_not_in_the_metadata() -> None:
    unit = AuditableFileUnit(unit_id="a.py", file_path="a.py", language="python")
    copy = dataclasses.replace(unit, content="y = 2")
    assert copy.language == "python"
    assert "language" not in unit.get_metadata()


def test_a_unit_has_no_children_unless_it_says_so() -> None:
    assert AuditableFileUnit(unit_id="a.py").children() == ()
    assert AuditableFileMetadataUnit(unit_id="a.py").children() == ()
