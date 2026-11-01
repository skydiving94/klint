"""Properties every auditable unit shares."""

from dataclasses import asdict

import pytest

from klint.catalog.code.language_neutral.units.file_metadata import (
    AuditableFileMetadataUnit,
)
from klint.catalog.code.python.units.package import AuditablePythonPackageUnit
from klint.catalog.domain_neutral.units.file import AuditableFileUnit
from klint.core.models.unit import AuditableUnit
from klint.core.models.unit_traits import UnitTraits

UNIT_CLASSES: list[type[AuditableUnit]] = [
    AuditableFileUnit,
    AuditableFileMetadataUnit,
    AuditablePythonPackageUnit,
]


@pytest.mark.parametrize("unit_class", UNIT_CLASSES)
def test_unit_language_is_unknown_by_default(unit_class: type[AuditableUnit]) -> None:
    assert unit_class(unit_id="u").language is None


@pytest.mark.parametrize("unit_class", UNIT_CLASSES)
def test_unit_language_comes_from_its_traits(unit_class: type[AuditableUnit]) -> None:
    assert (
        unit_class(unit_id="u", traits=UnitTraits(language="python")).language
        == "python"
    )


def test_unit_traits_are_keyword_only() -> None:
    # A positional second argument is still the unit's own first field.
    unit = AuditableFileUnit("a.py", "x = 1")
    assert unit.content == "x = 1"
    assert unit.traits == UnitTraits()


def test_unit_language_is_read_only() -> None:
    unit = AuditableFileUnit(unit_id="a.py", traits=UnitTraits(language="python"))
    with pytest.raises(AttributeError):
        unit.language = "go"  # type: ignore[misc]
    assert unit.language == "python"


def test_unit_language_is_not_in_the_context() -> None:
    unit = AuditableFileUnit(
        unit_id="a.py", file_path="a.py", traits=UnitTraits(language="python")
    )
    assert "language" not in asdict(unit.get_context())


def test_a_unit_has_no_children_unless_it_says_so() -> None:
    assert AuditableFileUnit(unit_id="a.py").children() == ()
    assert AuditableFileMetadataUnit(unit_id="a.py").children() == ()
