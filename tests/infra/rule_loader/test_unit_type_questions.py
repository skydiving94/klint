"""A rule's questions for some of its unit types, as a rules file writes them."""

import asyncio
from pathlib import Path

import pytest

from klint.core import KlintWarning
from klint.core.models.rules import AuditRule
from klint.core.models.units import UnitTraits
from klint.infra.rule_loader import JsonFileRuleSource, RulePackLoader
from tests.support.builders import UNIT_REGISTRY, write_json

_RULE = {
    "type": "choice",
    "question": "Is it clear?",
    "unit_types": ["file", "project_directory"],
}


def _load_rule(pack: Path) -> AuditRule:
    loader = RulePackLoader(
        [JsonFileRuleSource(pack)], [], UNIT_REGISTRY, frozenset({"python"})
    )
    (rule,) = asyncio.run(loader.load_rules(UnitTraits(language="python"), None))
    return rule


def test_a_unit_type_named_is_asked_its_own_question(tmp_path: Path) -> None:
    pack = write_json(
        tmp_path / "pack.json",
        {"clear": {**_RULE, "unit_type_to_question": {"file": "Is the file clear?"}}},
    )

    rule = _load_rule(pack)

    assert rule.find_question("file") == "Is the file clear?"
    assert rule.find_question("project_directory") == "Is it clear?"


@pytest.mark.parametrize("bad_value", ["Is it clear?", {"file": 3}, ["file"]])
def test_malformed_unit_type_questions_stop_with_an_error(
    tmp_path: Path, bad_value: object
) -> None:
    pack = write_json(
        tmp_path / "pack.json",
        {"broken": {**_RULE, "unit_type_to_question": bad_value}},
    )

    with pytest.raises(
        ValueError, match=r"^Rule 'broken' has invalid unit_type_to_question"
    ):
        _load_rule(pack)


def test_a_question_for_a_unit_type_the_rule_is_not_asked_about_is_warned_about(
    tmp_path: Path,
) -> None:
    pack = write_json(
        tmp_path / "pack.json",
        {"clear": {**_RULE, "unit_type_to_question": {"function": "Is it short?"}}},
    )

    with pytest.warns(KlintWarning, match=r"for \['function'\], which are not among"):
        rule = _load_rule(pack)

    assert rule.find_question("file") == "Is it clear?"
