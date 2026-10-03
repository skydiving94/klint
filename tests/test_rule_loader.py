"""Loading, merging and validating rule packs."""

import asyncio
import json
from pathlib import Path

import pytest

from src.core.models.question_type import QuestionType
from src.core.models.rule import AuditRule
from src.core.models.units import AuditableFileUnit, AuditableUnit
from src.infra.rule_loader.json_loader import JsonRuleLoader
from tests.helpers import DEFAULT_RULES, DIR_RULE, FILE_RULE, write_json


def _load(loader: JsonRuleLoader, custom: Path | None = None) -> dict[str, AuditRule]:
    return {rule.rule_id: rule for rule in asyncio.run(loader.load_rules(custom))}


def test_default_pack_loads_every_rule() -> None:
    raw = json.loads(DEFAULT_RULES.read_text(encoding="utf-8"))
    rules = _load(JsonRuleLoader(DEFAULT_RULES))
    assert list(rules) == list(raw)
    assert all(r.question_type is QuestionType.CHOICE for r in rules.values())
    assert all(r.target_unit_types == ["file"] for r in rules.values())
    assert rules["n_plus_1_query"].instructions == raw["n_plus_1_query"]["instructions"]


def test_custom_rules_merge_and_override_by_id(tmp_path: Path) -> None:
    custom = write_json(
        tmp_path / "custom.json",
        {
            "hardcoded_secrets": {**FILE_RULE, "instructions": "Overridden?"},
            "extra": FILE_RULE,
        },
    )
    defaults = _load(JsonRuleLoader(DEFAULT_RULES))
    merged = _load(JsonRuleLoader(DEFAULT_RULES), custom)
    assert len(merged) == len(defaults) + 1
    assert merged["hardcoded_secrets"].instructions == "Overridden?"
    assert merged["extra"].instructions == "Is it tidy?"
    assert merged["n_plus_1_query"] == defaults["n_plus_1_query"]


def test_klint_json_rules_block_is_read(tmp_path: Path) -> None:
    config = write_json(
        tmp_path / "klint.json",
        {"env": {"KEV_MODE": "local"}, "rules": {"only": FILE_RULE}},
    )
    assert list(_load(JsonRuleLoader(config))) == ["only"]


def test_entries_without_type_or_instructions_are_skipped(tmp_path: Path) -> None:
    pack = write_json(
        tmp_path / "pack.json",
        {
            "ok": FILE_RULE,
            "no_type": {"instructions": "x"},
            "no_text": {"type": "choice"},
            "junk": 1,
        },
    )
    assert list(_load(JsonRuleLoader(pack))) == ["ok"]


def test_target_unit_types_default_to_file_and_explicit_ones_are_kept(
    tmp_path: Path,
) -> None:
    pack = write_json(tmp_path / "pack.json", {"a": FILE_RULE, "b": DIR_RULE})
    rules = _load(JsonRuleLoader(pack))
    assert rules["a"].target_unit_types == ["file"]
    assert rules["b"].target_unit_types == ["project_directory"]


def test_unknown_target_unit_type_is_rejected(tmp_path: Path) -> None:
    pack = write_json(
        tmp_path / "pack.json", {"a": {**FILE_RULE, "target_unit_types": ["nope"]}}
    )
    with pytest.raises(ValueError, match="unknown target_unit_types"):
        _load(JsonRuleLoader(pack))


def test_unknown_question_type_is_rejected(tmp_path: Path) -> None:
    pack = write_json(tmp_path / "pack.json", {"a": {**FILE_RULE, "type": "essay"}})
    with pytest.raises(ValueError, match="essay"):
        _load(JsonRuleLoader(pack))


def test_missing_custom_file_raises(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        _load(JsonRuleLoader(DEFAULT_RULES), tmp_path / "absent.json")


def test_missing_default_file_gives_no_rules(tmp_path: Path) -> None:
    assert _load(JsonRuleLoader(tmp_path / "absent.json")) == {}


def test_builtin_unit_types_are_registered() -> None:
    known = set(AuditableUnit.known_unit_types())
    assert {"file", "file_metadata", "project_directory"} <= known


def test_rule_applies_only_to_its_target_unit_types() -> None:
    unit = AuditableFileUnit(unit_id="a.py", content="x = 1")
    file_rule = AuditRule("r", QuestionType.CHOICE, "?")
    dir_rule = AuditRule("r", QuestionType.CHOICE, "?", ["project_directory"])
    assert file_rule.is_applicable_to(unit)
    assert not dir_rule.is_applicable_to(unit)
