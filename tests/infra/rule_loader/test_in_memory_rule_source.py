"""Rules loaded from sources that read no file, such as packs held in memory."""

import asyncio
from pathlib import Path

import pytest

from klint.core.models.rule import AuditRule
from klint.core.models.unit_traits import UnitTraits
from klint.infra.rule_loader.json_file_rule_source import JsonFileRuleSource
from klint.infra.rule_loader.rule_pack_loader import RulePackLoader
from tests.support.builders import (
    FILE_RULE,
    UNIT_REGISTRY,
    build_rule_pack,
    write_json,
)
from tests.support.fakes import InMemoryRuleSource

PYTHON = UnitTraits(language="python")
JAVA = UnitTraits(language="java")
UNIDENTIFIED = UnitTraits(language=None)
TEST_PACK_LANGUAGES = frozenset({"python", "java"})


def _load(loader: RulePackLoader, traits: UnitTraits) -> dict[str, AuditRule]:
    rules = asyncio.run(loader.load_rules(traits))
    return {rule.rule_id: rule for rule in rules}


def test_rules_are_loaded_from_a_source_held_in_memory() -> None:
    shared = build_rule_pack("shared rules in memory", "tidy")
    python_only = build_rule_pack(
        "python rules in memory", "typed", languages=("python",)
    )
    loader = RulePackLoader(
        [InMemoryRuleSource(shared, python_only)],
        [InMemoryRuleSource(shared)],
        UNIT_REGISTRY,
        TEST_PACK_LANGUAGES,
    )

    python_rules = _load(loader, PYTHON)

    assert list(python_rules) == ["tidy", "typed"]
    assert python_rules["typed"].languages == ["python"]
    assert list(_load(loader, JAVA)) == ["tidy"]
    assert list(_load(loader, UNIDENTIFIED)) == ["tidy"]


def test_rule_problem_in_a_source_in_memory_names_where_the_pack_is_from() -> None:
    pack = build_rule_pack(
        "rules sent by the editor", "a", target_unit_types=("paragraph",)
    )
    loader = RulePackLoader(
        [InMemoryRuleSource(pack)], [], UNIT_REGISTRY, TEST_PACK_LANGUAGES
    )

    with pytest.raises(ValueError, match="in 'rules sent by the editor'"):
        _load(loader, PYTHON)


def test_custom_rules_from_a_source_in_memory_merge_last(tmp_path: Path) -> None:
    pack = write_json(tmp_path / "pack.json", {"a": FILE_RULE, "b": FILE_RULE})
    custom = InMemoryRuleSource(build_rule_pack("custom rules in memory", "a", "c"))

    loader = RulePackLoader(
        [JsonFileRuleSource(pack)], [], UNIT_REGISTRY, TEST_PACK_LANGUAGES
    )

    rules = asyncio.run(loader.load_rules(PYTHON, custom))

    assert [(rule.rule_id, rule.instructions) for rule in rules] == [
        ("a", "Is a kept?"),
        ("b", FILE_RULE["instructions"]),
        ("c", "Is c kept?"),
    ]
