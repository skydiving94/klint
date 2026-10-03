"""The unit registry."""

import pytest

from src.catalog.common.units.file import AuditableFileUnit
from src.core.registry import UnitRegistry


def test_new_registry_is_empty_and_registering_twice_is_harmless() -> None:
    registry = UnitRegistry()
    assert registry.known_unit_types() == []

    registry.register_unit(AuditableFileUnit)
    registry.register_unit(AuditableFileUnit)

    assert registry.known_unit_types() == ["file"]


def test_two_classes_cannot_share_a_unit_type() -> None:
    class Impostor(AuditableFileUnit):
        """Declares the same unit_type as the class it extends."""

    registry = UnitRegistry()
    registry.register_unit(AuditableFileUnit)

    with pytest.raises(ValueError, match="'file' is already registered"):
        registry.register_unit(Impostor)
