"""Loading, merging and validating rule packs, chosen by the traits of units."""

import asyncio
import json
from collections.abc import Collection, Sequence
from pathlib import Path
from typing import Any

import pytest

from klint.core.klint_warning import KlintWarning
from klint.core.models.question_type import QuestionType
from klint.core.models.rule import AuditRule
from klint.core.models.unit_traits import UnitTraits
from klint.core.registry import UnitRegistry
from klint.infra.rule_loader.json_file_rule_source import JsonFileRuleSource
from klint.infra.rule_loader.rule_pack_loader import RulePackLoader
from tests.support.builders import (
    DIR_RULE,
    FILE_RULE,
    KNOWN_LANGUAGES,
    UNIT_REGISTRY,
    write_json,
    write_text,
)
from tests.support.paths import (
    BUILT_IN_RULE_PACKS,
    FALLBACK_RULE_PACKS,
    PYTHON_PACKAGE_RULE_PACK,
    REACT_RULE_PACK,
)

PYTHON = UnitTraits(language="python")
TYPESCRIPT = UnitTraits(language="typescript")
JAVA = UnitTraits(language="java")
UNIDENTIFIED = UnitTraits(language=None)
# The languages a file can be identified as, for the packs written here.
TEST_PACK_LANGUAGES = frozenset({"python", "typescript", "javascript", "java", "go"})


def _build_sources(rule_packs: Sequence[Path]) -> list[JsonFileRuleSource]:
    return [JsonFileRuleSource(path) for path in rule_packs]


def _build_loader(
    rule_packs: Sequence[Path],
    fallback_rule_packs: Sequence[Path] = (),
    known_languages: Collection[str] = TEST_PACK_LANGUAGES,
    project_rule_packs: Sequence[Path] = (),
    unit_registry: UnitRegistry = UNIT_REGISTRY,
) -> RulePackLoader:
    return RulePackLoader(
        _build_sources(rule_packs),
        _build_sources(fallback_rule_packs),
        unit_registry,
        known_languages,
        _build_sources(project_rule_packs),
    )


def _build_built_in_loader() -> RulePackLoader:
    return _build_loader(BUILT_IN_RULE_PACKS, FALLBACK_RULE_PACKS, KNOWN_LANGUAGES)


def _load_rule_id_to_rule(
    loader: RulePackLoader, traits: UnitTraits = PYTHON, custom: Path | None = None
) -> dict[str, AuditRule]:
    custom_rule_source = (
        None if custom is None else JsonFileRuleSource(custom, is_required=True)
    )
    rules = asyncio.run(loader.load_rules(traits, custom_rule_source))
    return {rule.rule_id: rule for rule in rules}


def _list_rule_ids_in(*packs: Path) -> list[str]:
    """Return the IDs of the rules written in ``packs``, in file order."""
    rule_ids: list[str] = []
    for pack in packs:
        rule_ids.extend(json.loads(pack.read_text(encoding="utf-8"))["rules"])
    return rule_ids


def _build_pack(
    applies_to: dict[str, Any], rule_id_to_spec: dict[str, Any]
) -> dict[str, Any]:
    return {"applies_to": applies_to, "rules": rule_id_to_spec}


def test_rules_keep_the_order_of_the_chosen_packs_and_of_each_pack(
    tmp_path: Path,
) -> None:
    first = write_json(tmp_path / "first.json", {"b": FILE_RULE, "a": FILE_RULE})
    python_only = write_json(
        tmp_path / "python.json",
        _build_pack({"languages": ["python"]}, {"c": FILE_RULE}),
    )
    typescript_only = write_json(
        tmp_path / "typescript.json",
        _build_pack({"languages": ["typescript"]}, {"d": FILE_RULE}),
    )
    last = write_json(tmp_path / "last.json", {"e": FILE_RULE})
    loader = _build_loader([first, python_only, typescript_only, last])

    # The judge is asked the rules in this order.
    assert list(_load_rule_id_to_rule(loader, TYPESCRIPT)) == ["b", "a", "d", "e"]
    assert list(_load_rule_id_to_rule(loader, PYTHON)) == ["b", "a", "c", "e"]


def test_built_in_typescript_file_rules_are_choice_questions_about_files() -> None:
    rule_id_to_rule = _load_rule_id_to_rule(_build_built_in_loader(), TYPESCRIPT)

    assert rule_id_to_rule
    assert all(r.question_type is QuestionType.CHOICE for r in rule_id_to_rule.values())
    assert all(r.unit_types == ["file"] for r in rule_id_to_rule.values())


def test_built_in_packs_are_chosen_by_the_language_of_the_file() -> None:
    loader = _build_built_in_loader()
    shared = set(_list_rule_ids_in(*FALLBACK_RULE_PACKS))
    react = set(_list_rule_ids_in(REACT_RULE_PACK))
    python_project = set(_list_rule_ids_in(PYTHON_PACKAGE_RULE_PACK))

    assert set(_load_rule_id_to_rule(loader, PYTHON)) == shared | python_project
    assert set(_load_rule_id_to_rule(loader, TYPESCRIPT)) == shared | react
    assert set(_load_rule_id_to_rule(loader, JAVA)) == shared
    assert set(_load_rule_id_to_rule(loader, UNIDENTIFIED)) == shared


def test_file_of_unidentified_language_is_asked_only_the_fallback_packs(
    tmp_path: Path,
) -> None:
    shared = write_json(
        tmp_path / "shared.json", _build_pack({}, {"for_code": FILE_RULE})
    )
    fallback = write_json(
        tmp_path / "fallback.json", _build_pack({}, {"for_prose": FILE_RULE})
    )
    loader = _build_loader([shared], [fallback])

    assert list(_load_rule_id_to_rule(loader, UNIDENTIFIED)) == ["for_prose"]
    assert list(_load_rule_id_to_rule(loader, PYTHON)) == ["for_code"]


def test_pack_without_a_header_loads_for_every_identified_language(
    tmp_path: Path,
) -> None:
    pack = write_json(tmp_path / "pack.json", {"a": FILE_RULE})
    loader = _build_loader([pack])

    assert list(_load_rule_id_to_rule(loader, PYTHON)) == ["a"]
    assert list(_load_rule_id_to_rule(loader, JAVA)) == ["a"]
    assert _load_rule_id_to_rule(loader, UNIDENTIFIED) == {}
    assert _load_rule_id_to_rule(loader, PYTHON)["a"].languages == []


def test_rule_inherits_the_languages_of_its_pack(tmp_path: Path) -> None:
    pack = write_json(
        tmp_path / "pack.json",
        _build_pack({"languages": ["typescript", "javascript"]}, {"a": FILE_RULE}),
    )

    rule_id_to_rule = _load_rule_id_to_rule(_build_loader([pack]), TYPESCRIPT)

    assert rule_id_to_rule["a"].languages == ["typescript", "javascript"]
    assert _load_rule_id_to_rule(_build_loader([pack]), PYTHON) == {}


def test_rule_may_narrow_the_languages_of_its_pack(tmp_path: Path) -> None:
    pack = write_json(
        tmp_path / "pack.json",
        _build_pack(
            {"languages": ["typescript", "javascript"]},
            {"a": {**FILE_RULE, "languages": ["typescript"]}},
        ),
    )

    assert _load_rule_id_to_rule(_build_loader([pack]), TYPESCRIPT)["a"].languages == [
        "typescript"
    ]


def test_rule_naming_a_language_its_pack_leaves_out_is_warned_about(
    tmp_path: Path,
) -> None:
    pack = write_json(
        tmp_path / "pack.json",
        _build_pack(
            {"languages": ["python"]},
            {
                "partly_out": {**FILE_RULE, "languages": ["python", "go"]},
                "all_out": {**FILE_RULE, "languages": ["go"]},
            },
        ),
    )

    with pytest.warns(KlintWarning, match=r"names languages \['go'\]") as caught:
        rule_id_to_rule = _load_rule_id_to_rule(_build_loader([pack]), PYTHON)

    assert len(caught) == 2
    # A rule left with no language of its pack never runs, so it is dropped.
    assert list(rule_id_to_rule) == ["partly_out"]
    assert rule_id_to_rule["partly_out"].languages == ["python"]


def test_rules_of_a_pack_that_is_not_chosen_are_not_read(tmp_path: Path) -> None:
    pack = write_json(
        tmp_path / "pack.json",
        _build_pack(
            {"languages": ["typescript"]},
            {"broken": {**FILE_RULE, "unit_types": ["nope"]}},
        ),
    )
    loader = _build_loader([pack])

    assert _load_rule_id_to_rule(loader, PYTHON) == {}
    with pytest.raises(ValueError, match="unknown unit_types"):
        _load_rule_id_to_rule(loader, TYPESCRIPT)


def test_each_pack_is_read_once_however_many_loads_use_it(tmp_path: Path) -> None:
    pack = write_json(
        tmp_path / "pack.json", {"typo": {**FILE_RULE, "langauges": ["python"]}}
    )
    loader = _build_loader([pack])

    with pytest.warns(KlintWarning, match="unknown fields"):
        _load_rule_id_to_rule(loader, PYTHON)

    # No warning the second time: an unexpected one fails the test.
    assert list(_load_rule_id_to_rule(loader, JAVA)) == ["typo"]


def test_header_with_an_unknown_field_is_kept_with_a_warning(tmp_path: Path) -> None:
    pack = write_json(
        tmp_path / "pack.json",
        _build_pack({"languages": ["python"], "tags": ["security"]}, {"a": FILE_RULE}),
    )

    with pytest.warns(KlintWarning, match=r"header .* unknown fields \['tags'\]"):
        rule_id_to_rule = _load_rule_id_to_rule(_build_loader([pack]), PYTHON)

    assert rule_id_to_rule["a"].languages == ["python"]


def test_header_naming_an_unknown_language_is_kept_with_a_warning(
    tmp_path: Path,
) -> None:
    pack = write_json(
        tmp_path / "pack.json",
        _build_pack({"languages": ["python", "pyhton"]}, {"a": FILE_RULE}),
    )

    with pytest.warns(KlintWarning, match=r"header .* unknown languages \['pyhton'\]"):
        rule_id_to_rule = _load_rule_id_to_rule(_build_loader([pack]), PYTHON)

    assert rule_id_to_rule["a"].languages == ["python", "pyhton"]


@pytest.mark.parametrize(
    "applies_to", ["python", {"languages": "python"}, {"languages": []}]
)
def test_malformed_header_stops_with_an_error_naming_the_file(
    tmp_path: Path, applies_to: object
) -> None:
    pack = write_json(
        tmp_path / "pack.json", {"applies_to": applies_to, "rules": {"a": FILE_RULE}}
    )

    with pytest.raises(ValueError, match=r"pack\.json' has an invalid applies_to"):
        _load_rule_id_to_rule(_build_loader([pack]), PYTHON)


def test_custom_rules_override_any_pack_by_id_and_add_new_ones(
    tmp_path: Path,
) -> None:
    first = write_json(tmp_path / "first.json", {"a": FILE_RULE, "b": FILE_RULE})
    second = write_json(tmp_path / "second.json", {"c": FILE_RULE})
    custom = write_json(
        tmp_path / "custom.json",
        {
            "a": {**FILE_RULE, "question": "Custom?"},
            "extra": {**FILE_RULE, "question": "Extra?"},
        },
    )

    defaults = _load_rule_id_to_rule(_build_loader([first, second]))
    rule_id_to_rule = _load_rule_id_to_rule(
        _build_loader([first, second]), custom=custom
    )

    assert list(rule_id_to_rule) == ["a", "b", "c", "extra"]
    assert rule_id_to_rule["a"].question == "Custom?"
    assert rule_id_to_rule["extra"].question == "Extra?"
    assert (rule_id_to_rule["b"], rule_id_to_rule["c"]) == (
        defaults["b"],
        defaults["c"],
    )


@pytest.mark.parametrize("traits", [PYTHON, UNIDENTIFIED])
def test_custom_rules_merge_whatever_the_traits(
    tmp_path: Path, traits: UnitTraits
) -> None:
    pack = write_json(tmp_path / "pack.json", {"for_code": FILE_RULE})
    fallback = write_json(tmp_path / "fallback.json", {"for_prose": FILE_RULE})
    custom = write_json(tmp_path / "custom.json", {"house_rule": FILE_RULE})

    assert "house_rule" in _load_rule_id_to_rule(
        _build_loader([pack], [fallback]), traits, custom
    )


def test_klint_json_rules_block_is_read(tmp_path: Path) -> None:
    config = write_json(
        tmp_path / "klint.json",
        {"env": {"KLINT_JUDGE_MODE": "local"}, "rules": {"only": FILE_RULE}},
    )
    assert list(_load_rule_id_to_rule(_build_loader([config]))) == ["only"]


def test_entries_without_type_or_question_are_skipped_with_a_warning(
    tmp_path: Path,
) -> None:
    pack = write_json(
        tmp_path / "pack.json",
        {
            "ok": FILE_RULE,
            "no_type": {"question": "x"},
            "no_text": {"type": "choice"},
            "junk": 1,
        },
    )
    with pytest.warns(KlintWarning, match="needs both 'type' and") as caught:
        rule_id_to_rule = _load_rule_id_to_rule(_build_loader([pack]))

    assert list(rule_id_to_rule) == ["ok"]
    assert len(caught) == 3


def test_rule_naming_an_unknown_language_is_kept_with_a_warning(
    tmp_path: Path,
) -> None:
    pack = write_json(
        tmp_path / "pack.json",
        {"typo": {**FILE_RULE, "languages": ["pyhton", "Python"]}},
    )

    with pytest.warns(KlintWarning, match=r"'typo' .* unknown languages \['pyhton'\]"):
        rule_id_to_rule = _load_rule_id_to_rule(_build_loader([pack]))

    assert rule_id_to_rule["typo"].languages == ["pyhton", "Python"]


def test_unknown_rule_field_is_ignored_with_a_warning(tmp_path: Path) -> None:
    pack = write_json(
        tmp_path / "pack.json", {"typo": {**FILE_RULE, "langauges": ["python"]}}
    )

    with pytest.warns(KlintWarning, match=r"unknown fields \['langauges'\]"):
        rule_id_to_rule = _load_rule_id_to_rule(_build_loader([pack]))

    assert rule_id_to_rule["typo"].languages == []


def test_keys_beside_a_rules_block_are_not_rules(tmp_path: Path) -> None:
    pack = write_json(
        tmp_path / "pack.json",
        {
            "env": {"KLINT_JUDGE_MODE": "local"},
            "fallback_rule_packs": ["docs.json"],
            "rules": {"a": FILE_RULE},
        },
    )

    # No warning either: an unexpected one fails the test.
    assert list(_load_rule_id_to_rule(_build_loader([pack]))) == ["a"]


def test_every_key_of_a_flat_file_but_its_header_is_a_rule(tmp_path: Path) -> None:
    pack = write_json(
        tmp_path / "pack.json",
        {"applies_to": {}, "env": {"KLINT_JUDGE_MODE": "local"}, "a": FILE_RULE},
    )

    with pytest.warns(KlintWarning, match="Rule 'env' .* is skipped"):
        assert list(_load_rule_id_to_rule(_build_loader([pack]))) == ["a"]


def test_project_rules_merge_over_the_packs_for_every_file_and_custom_ones_over_them(
    tmp_path: Path,
) -> None:
    pack = write_json(
        tmp_path / "pack.json",
        _build_pack(
            {"languages": ["python"]}, {"shared": FILE_RULE, "pack_only": FILE_RULE}
        ),
    )
    project = write_json(
        tmp_path / "klint.json",
        {
            "env": {"KLINT_JUDGE_MODE": "local"},
            "rules": {
                "shared": {**FILE_RULE, "question": "From the project?"},
                "project_only": FILE_RULE,
            },
        },
    )
    custom = write_json(
        tmp_path / "custom.json",
        {"project_only": {**FILE_RULE, "question": "From --rules?"}},
    )
    loader = _build_loader([pack], project_rule_packs=[project])

    python_rules = _load_rule_id_to_rule(loader, PYTHON, custom)
    java_rules = _load_rule_id_to_rule(loader, JAVA)

    assert {rule_id: rule.question for rule_id, rule in python_rules.items()} == {
        "shared": "From the project?",
        "pack_only": FILE_RULE["question"],
        "project_only": "From --rules?",
    }
    assert list(java_rules) == ["shared", "project_only"]


@pytest.mark.parametrize(
    ("content", "reason"),
    [("{not json", "is not valid JSON"), ("[]", "must be a JSON object")],
)
def test_file_that_cannot_be_read_as_rules_stops_with_an_error_naming_it(
    tmp_path: Path, content: str, reason: str
) -> None:
    pack = write_text(tmp_path / "pack.json", content)

    with pytest.raises(ValueError, match=rf"pack\.json' {reason}"):
        _load_rule_id_to_rule(_build_loader([pack]))


def test_unit_types_default_to_file_and_explicit_ones_are_kept(
    tmp_path: Path,
) -> None:
    pack = write_json(tmp_path / "pack.json", {"a": FILE_RULE, "b": DIR_RULE})
    rule_id_to_rule = _load_rule_id_to_rule(_build_loader([pack]))
    assert rule_id_to_rule["a"].unit_types == ["file"]
    assert rule_id_to_rule["b"].unit_types == ["project_directory"]


def test_unknown_unit_type_is_rejected(tmp_path: Path) -> None:
    pack = write_json(
        tmp_path / "pack.json", {"a": {**FILE_RULE, "unit_types": ["nope"]}}
    )
    with pytest.raises(ValueError, match="unknown unit_types"):
        _load_rule_id_to_rule(_build_loader([pack]))


def test_unknown_question_type_is_rejected(tmp_path: Path) -> None:
    pack = write_json(tmp_path / "pack.json", {"a": {**FILE_RULE, "type": "essay"}})
    with pytest.raises(ValueError, match="essay"):
        _load_rule_id_to_rule(_build_loader([pack]))


@pytest.mark.parametrize(
    ("field_name", "bad_value", "message"),
    [
        ("type", "yesno", "has unknown type 'yesno'"),
        ("type", 1, "has unknown type 1"),
        ("unit_types", "file", "has invalid unit_types 'file'"),
        ("unit_types", ["nope"], r"has unknown unit_types \['nope'\]"),
        ("question", 7, "has invalid question 7"),
    ],
)
def test_malformed_rule_stops_with_an_error_naming_the_rule_and_the_file(
    tmp_path: Path, field_name: str, bad_value: object, message: str
) -> None:
    pack = write_json(
        tmp_path / "pack.json", {"broken": {**FILE_RULE, field_name: bad_value}}
    )

    with pytest.raises(
        ValueError, match=rf"^Rule 'broken' {message} in '.*pack\.json'"
    ):
        _load_rule_id_to_rule(_build_loader([pack]))


def test_malformed_rule_in_a_pack_that_is_not_chosen_stops_nothing(
    tmp_path: Path,
) -> None:
    pack = write_json(
        tmp_path / "pack.json",
        _build_pack(
            {"languages": ["typescript"]},
            {"typo": {"type": "choice"}, "broken": {**FILE_RULE, "type": "yesno"}},
        ),
    )
    loader = _build_loader([pack])

    # No warning either: an unexpected one fails the test.
    assert _load_rule_id_to_rule(loader, PYTHON) == {}
    with (
        pytest.warns(KlintWarning, match="'typo' .* is skipped"),
        pytest.raises(ValueError, match="has unknown type 'yesno'"),
    ):
        _load_rule_id_to_rule(loader, TYPESCRIPT)


def test_missing_custom_file_raises(tmp_path: Path) -> None:
    pack = write_json(tmp_path / "pack.json", {"a": FILE_RULE})

    with pytest.raises(FileNotFoundError, match="Rules file does not exist"):
        _load_rule_id_to_rule(_build_loader([pack]), custom=tmp_path / "absent.json")


def test_missing_pack_gives_no_rules(tmp_path: Path) -> None:
    absent = tmp_path / "absent.json"
    assert _load_rule_id_to_rule(_build_loader([absent])) == {}
    assert _load_rule_id_to_rule(_build_loader([], [absent]), UNIDENTIFIED) == {}


def test_several_packs_are_merged_in_order(tmp_path: Path) -> None:
    first = write_json(
        tmp_path / "first.json",
        {"shared": {**FILE_RULE, "question": "From first?"}, "a": FILE_RULE},
    )
    second = write_json(
        tmp_path / "second.json",
        {"shared": {**FILE_RULE, "question": "From second?"}, "b": FILE_RULE},
    )

    rule_id_to_rule = _load_rule_id_to_rule(_build_loader([first, second]))

    assert list(rule_id_to_rule) == ["shared", "a", "b"]
    assert rule_id_to_rule["shared"].question == "From second?"


def test_missing_pack_is_skipped_among_several(tmp_path: Path) -> None:
    present = write_json(tmp_path / "present.json", {"a": FILE_RULE})

    rule_id_to_rule = _load_rule_id_to_rule(
        _build_loader([tmp_path / "absent.json", present])
    )

    assert list(rule_id_to_rule) == ["a"]


def test_languages_tags_and_unit_tags_are_read_from_a_rule(tmp_path: Path) -> None:
    pack = write_json(
        tmp_path / "pack.json",
        {
            "scoped": {
                **FILE_RULE,
                "languages": ["python"],
                "tags": ["security"],
                "unit_tags": ["backend"],
            },
            "plain": FILE_RULE,
            "empty": {**FILE_RULE, "languages": [], "tags": [], "unit_tags": []},
        },
    )

    rule_id_to_rule = _load_rule_id_to_rule(_build_loader([pack]))

    assert rule_id_to_rule["scoped"].languages == ["python"]
    assert rule_id_to_rule["scoped"].tags == ["security"]
    assert rule_id_to_rule["scoped"].unit_tags == ["backend"]
    for plain_rule in (rule_id_to_rule["plain"], rule_id_to_rule["empty"]):
        assert (plain_rule.languages, plain_rule.tags, plain_rule.unit_tags) == (
            [],
            [],
            [],
        )
    assert rule_id_to_rule["plain"].unit_types == ["file"]


@pytest.mark.parametrize("field_name", ["languages", "tags", "unit_tags"])
@pytest.mark.parametrize("bad_value", ["python", ["python", 3], {"a": 1}, None])
def test_malformed_languages_or_tags_are_rejected(
    tmp_path: Path, field_name: str, bad_value: object
) -> None:
    pack = write_json(
        tmp_path / "pack.json", {"broken": {**FILE_RULE, field_name: bad_value}}
    )
    with pytest.raises(ValueError, match=f"Rule 'broken' has invalid {field_name}"):
        _load_rule_id_to_rule(_build_loader([pack]))


def test_built_in_python_project_rules_are_limited_to_python() -> None:
    rule_id_to_rule = _load_rule_id_to_rule(
        _build_loader([PYTHON_PACKAGE_RULE_PACK], (), KNOWN_LANGUAGES), PYTHON
    )

    assert rule_id_to_rule
    assert all(rule.languages == ["python"] for rule in rule_id_to_rule.values())


def test_built_in_react_rules_are_limited_to_typescript_and_javascript() -> None:
    rule_id_to_rule = _load_rule_id_to_rule(
        _build_loader([REACT_RULE_PACK], (), KNOWN_LANGUAGES), TYPESCRIPT
    )

    assert rule_id_to_rule
    assert all(
        rule.languages == ["typescript", "javascript"]
        for rule in rule_id_to_rule.values()
    )


def test_built_in_rules_set_no_tags() -> None:
    loader = _build_built_in_loader()
    rule_id_to_rule = {
        **_load_rule_id_to_rule(loader, PYTHON),
        **_load_rule_id_to_rule(loader, TYPESCRIPT),
    }

    assert all(rule.tags == [] for rule in rule_id_to_rule.values())


def test_rule_loading_only_accepts_registered_unit_types(tmp_path: Path) -> None:
    pack = write_json(
        tmp_path / "pack.json", {"a": {**FILE_RULE, "unit_types": ["file"]}}
    )
    loader = _build_loader([pack], unit_registry=UnitRegistry())

    with pytest.raises(ValueError, match="unknown unit_types"):
        asyncio.run(loader.load_rules(PYTHON))


def test_built_in_backend_and_react_rules_are_limited_to_their_side() -> None:
    loader = _build_built_in_loader()
    backend_rule_ids = _list_rule_ids_in(BUILT_IN_RULE_PACKS[0])
    react_rule_ids = _list_rule_ids_in(REACT_RULE_PACK)

    rule_id_to_rule = {
        **_load_rule_id_to_rule(loader, PYTHON),
        **_load_rule_id_to_rule(loader, TYPESCRIPT),
    }

    assert backend_rule_ids
    assert react_rule_ids
    for rule_id, rule in rule_id_to_rule.items():
        if rule_id in backend_rule_ids:
            assert rule.unit_tags == ["backend"], rule_id
        elif rule_id in react_rule_ids:
            assert rule.unit_tags == ["frontend"], rule_id
        else:
            assert rule.unit_tags == [], rule_id
