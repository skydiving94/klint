"""The unit registry and how rule loading depends on it."""

import asyncio
from pathlib import Path

import pytest

from src.catalog.common.units.file import AuditableFileUnit
from src.core.registry import UnitRegistry
from src.infra.rule_loader.json_loader import JsonRuleLoader
from tests.helpers import FILE_RULE, build_unit_registry, write_json


def test_built_in_suites_register_their_unit_types() -> None:
    assert build_unit_registry().known_unit_types() == [
        "file",
        "file_metadata",
        "project_directory",
    ]


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


def test_rule_loading_only_accepts_registered_unit_types(tmp_path: Path) -> None:
    pack = write_json(
        tmp_path / "pack.json", {"a": {**FILE_RULE, "target_unit_types": ["file"]}}
    )
    loader = JsonRuleLoader([pack], UnitRegistry())

    with pytest.raises(ValueError, match="unknown target_unit_types"):
        asyncio.run(loader.load_rules())
