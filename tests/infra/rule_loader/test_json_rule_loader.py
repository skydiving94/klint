"""Loading, merging and validating rule packs, chosen by the traits of files."""

import asyncio
import json
from collections.abc import Collection, Sequence
from pathlib import Path
from typing import Any

import pytest

from klint.core.klint_warning import KlintWarning
from klint.core.models.file_traits import FileTraits
from klint.core.models.question_type import QuestionType
from klint.core.models.rule import AuditRule
from klint.core.registry import UnitRegistry
from klint.infra.rule_loader.json_rule_loader import JsonRuleLoader
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
    PYTHON_PROJECT_RULE_PACK,
    REACT_RULE_PACK,
)

PYTHON = FileTraits(language="python")
TYPESCRIPT = FileTraits(language="typescript")
JAVA = FileTraits(language="java")
UNIDENTIFIED = FileTraits(language=None)
# The languages a file can be identified as, for the packs written here.
TEST_PACK_LANGUAGES = frozenset({"python", "typescript", "javascript", "java", "go"})


def _loader(
    rule_packs: Sequence[Path],
    fallback_rule_packs: Sequence[Path] = (),
    known_languages: Collection[str] = TEST_PACK_LANGUAGES,
) -> JsonRuleLoader:
    return JsonRuleLoader(
        rule_packs, fallback_rule_packs, UNIT_REGISTRY, known_languages
    )


def _built_in_loader() -> JsonRuleLoader:
    return _loader(BUILT_IN_RULE_PACKS, FALLBACK_RULE_PACKS, KNOWN_LANGUAGES)


def _load(
    loader: JsonRuleLoader, traits: FileTraits = PYTHON, custom: Path | None = None
) -> dict[str, AuditRule]:
    rules = asyncio.run(loader.load_rules(traits, custom))
    return {rule.rule_id: rule for rule in rules}


def _rule_ids_in(*packs: Path) -> list[str]:
    """Return the IDs of the rules written in ``packs``, in file order."""
    rule_ids: list[str] = []
    for pack in packs:
        rule_ids.extend(json.loads(pack.read_text(encoding="utf-8"))["rules"])
    return rule_ids


def _pack(applies_to: dict[str, Any], rules: dict[str, Any]) -> dict[str, Any]:
    return {"applies_to": applies_to, "rules": rules}


def test_rules_keep_the_order_of_the_chosen_packs_and_of_each_pack(
    tmp_path: Path,
) -> None:
    first = write_json(tmp_path / "first.json", {"b": FILE_RULE, "a": FILE_RULE})
    python_only = write_json(
        tmp_path / "python.json", _pack({"languages": ["python"]}, {"c": FILE_RULE})
    )
    typescript_only = write_json(
        tmp_path / "typescript.json",
        _pack({"languages": ["typescript"]}, {"d": FILE_RULE}),
    )
    last = write_json(tmp_path / "last.json", {"e": FILE_RULE})
    loader = _loader([first, python_only, typescript_only, last])

    # The judge is asked the rules in this order.
    assert list(_load(loader, TYPESCRIPT)) == ["b", "a", "d", "e"]
    assert list(_load(loader, PYTHON)) == ["b", "a", "c", "e"]


def test_built_in_typescript_file_rules_are_choice_questions_about_files() -> None:
    rules = _load(_built_in_loader(), TYPESCRIPT)

    assert rules
    assert all(r.question_type is QuestionType.CHOICE for r in rules.values())
    assert all(r.target_unit_types == ["file"] for r in rules.values())


def test_built_in_packs_are_chosen_by_the_language_of_the_file() -> None:
    loader = _built_in_loader()
    shared = set(_rule_ids_in(*FALLBACK_RULE_PACKS))
    react = set(_rule_ids_in(REACT_RULE_PACK))
    python_project = set(_rule_ids_in(PYTHON_PROJECT_RULE_PACK))

    assert set(_load(loader, PYTHON)) == shared | python_project
    assert set(_load(loader, TYPESCRIPT)) == shared | react
    assert set(_load(loader, JAVA)) == shared
    assert set(_load(loader, UNIDENTIFIED)) == shared


def test_file_of_unidentified_language_is_asked_only_the_fallback_packs(
    tmp_path: Path,
) -> None:
    shared = write_json(tmp_path / "shared.json", _pack({}, {"for_code": FILE_RULE}))
    fallback = write_json(
        tmp_path / "fallback.json", _pack({}, {"for_prose": FILE_RULE})
    )
    loader = _loader([shared], [fallback])

    assert list(_load(loader, UNIDENTIFIED)) == ["for_prose"]
    assert list(_load(loader, PYTHON)) == ["for_code"]


def test_pack_without_a_header_loads_for_every_identified_language(
    tmp_path: Path,
) -> None:
    pack = write_json(tmp_path / "pack.json", {"a": FILE_RULE})
    loader = _loader([pack])

    assert list(_load(loader, PYTHON)) == ["a"]
    assert list(_load(loader, JAVA)) == ["a"]
    assert _load(loader, UNIDENTIFIED) == {}
    assert _load(loader, PYTHON)["a"].languages == []


def test_rule_inherits_the_languages_of_its_pack(tmp_path: Path) -> None:
    pack = write_json(
        tmp_path / "pack.json",
        _pack({"languages": ["typescript", "javascript"]}, {"a": FILE_RULE}),
    )

    rules = _load(_loader([pack]), TYPESCRIPT)

    assert rules["a"].languages == ["typescript", "javascript"]
    assert _load(_loader([pack]), PYTHON) == {}


def test_rule_may_narrow_the_languages_of_its_pack(tmp_path: Path) -> None:
    pack = write_json(
        tmp_path / "pack.json",
        _pack(
            {"languages": ["typescript", "javascript"]},
            {"a": {**FILE_RULE, "languages": ["typescript"]}},
        ),
    )

    assert _load(_loader([pack]), TYPESCRIPT)["a"].languages == ["typescript"]


def test_rule_naming_a_language_its_pack_leaves_out_is_warned_about(
    tmp_path: Path,
) -> None:
    pack = write_json(
        tmp_path / "pack.json",
        _pack(
            {"languages": ["python"]},
            {
                "partly_out": {**FILE_RULE, "languages": ["python", "go"]},
                "all_out": {**FILE_RULE, "languages": ["go"]},
            },
        ),
    )

    with pytest.warns(KlintWarning, match=r"names languages \['go'\]") as caught:
        rules = _load(_loader([pack]), PYTHON)

    assert len(caught) == 2
    # A rule left with no language of its pack never runs, so it is dropped.
    assert list(rules) == ["partly_out"]
    assert rules["partly_out"].languages == ["python"]


def test_rules_of_a_pack_that_is_not_chosen_are_not_read(tmp_path: Path) -> None:
    pack = write_json(
        tmp_path / "pack.json",
        _pack(
            {"languages": ["typescript"]},
            {"broken": {**FILE_RULE, "target_unit_types": ["nope"]}},
        ),
    )
    loader = _loader([pack])

    assert _load(loader, PYTHON) == {}
    with pytest.raises(ValueError, match="unknown target_unit_types"):
        _load(loader, TYPESCRIPT)


def test_each_pack_is_read_once_however_many_loads_use_it(tmp_path: Path) -> None:
    pack = write_json(
        tmp_path / "pack.json", {"typo": {**FILE_RULE, "langauges": ["python"]}}
    )
    loader = _loader([pack])

    with pytest.warns(KlintWarning, match="unknown fields"):
        _load(loader, PYTHON)

    # No warning the second time: an unexpected one fails the test.
    assert list(_load(loader, JAVA)) == ["typo"]


def test_header_with_an_unknown_field_is_kept_with_a_warning(tmp_path: Path) -> None:
    pack = write_json(
        tmp_path / "pack.json",
        _pack({"languages": ["python"], "tags": ["security"]}, {"a": FILE_RULE}),
    )

    with pytest.warns(KlintWarning, match=r"header .* unknown fields \['tags'\]"):
        rules = _load(_loader([pack]), PYTHON)

    assert rules["a"].languages == ["python"]


def test_header_naming_an_unknown_language_is_kept_with_a_warning(
    tmp_path: Path,
) -> None:
    pack = write_json(
        tmp_path / "pack.json",
        _pack({"languages": ["python", "pyhton"]}, {"a": FILE_RULE}),
    )

    with pytest.warns(KlintWarning, match=r"header .* unknown languages \['pyhton'\]"):
        rules = _load(_loader([pack]), PYTHON)

    assert rules["a"].languages == ["python", "pyhton"]


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
        _load(_loader([pack]), PYTHON)


def test_custom_rules_override_any_pack_by_id_and_add_new_ones(
    tmp_path: Path,
) -> None:
    first = write_json(tmp_path / "first.json", {"a": FILE_RULE, "b": FILE_RULE})
    second = write_json(tmp_path / "second.json", {"c": FILE_RULE})
    custom = write_json(
        tmp_path / "custom.json",
        {
            "a": {**FILE_RULE, "instructions": "Custom?"},
            "extra": {**FILE_RULE, "instructions": "Extra?"},
        },
    )

    defaults = _load(_loader([first, second]))
    rules = _load(_loader([first, second]), custom=custom)

    assert list(rules) == ["a", "b", "c", "extra"]
    assert rules["a"].instructions == "Custom?"
    assert rules["extra"].instructions == "Extra?"
    assert (rules["b"], rules["c"]) == (defaults["b"], defaults["c"])


@pytest.mark.parametrize("traits", [PYTHON, UNIDENTIFIED])
def test_custom_rules_merge_whatever_the_traits(
    tmp_path: Path, traits: FileTraits
) -> None:
    pack = write_json(tmp_path / "pack.json", {"for_code": FILE_RULE})
    fallback = write_json(tmp_path / "fallback.json", {"for_prose": FILE_RULE})
    custom = write_json(tmp_path / "custom.json", {"house_rule": FILE_RULE})

    assert "house_rule" in _load(_loader([pack], [fallback]), traits, custom)


def test_klint_json_rules_block_is_read(tmp_path: Path) -> None:
    config = write_json(
        tmp_path / "klint.json",
        {"env": {"KEV_MODE": "local"}, "rules": {"only": FILE_RULE}},
    )
    assert list(_load(_loader([config]))) == ["only"]


def test_entries_without_type_or_instructions_are_skipped_with_a_warning(
    tmp_path: Path,
) -> None:
    pack = write_json(
        tmp_path / "pack.json",
        {
            "ok": FILE_RULE,
            "no_type": {"instructions": "x"},
            "no_text": {"type": "choice"},
            "junk": 1,
        },
    )
    with pytest.warns(KlintWarning, match="needs both 'type' and") as caught:
        rules = _load(_loader([pack]))

    assert list(rules) == ["ok"]
    assert len(caught) == 3


def test_rule_naming_an_unknown_language_is_kept_with_a_warning(
    tmp_path: Path,
) -> None:
    pack = write_json(
        tmp_path / "pack.json",
        {"typo": {**FILE_RULE, "languages": ["pyhton", "Python"]}},
    )

    with pytest.warns(KlintWarning, match=r"'typo' .* unknown languages \['pyhton'\]"):
        rules = _load(_loader([pack]))

    assert rules["typo"].languages == ["pyhton", "Python"]


def test_unknown_rule_field_is_ignored_with_a_warning(tmp_path: Path) -> None:
    pack = write_json(
        tmp_path / "pack.json", {"typo": {**FILE_RULE, "langauges": ["python"]}}
    )

    with pytest.warns(KlintWarning, match=r"unknown fields \['langauges'\]"):
        rules = _load(_loader([pack]))

    assert rules["typo"].languages == []


def test_settings_beside_flat_rules_are_not_taken_for_rules(tmp_path: Path) -> None:
    pack = write_json(
        tmp_path / "pack.json",
        {
            "env": {"KEV_MODE": "local"},
            "fallback_rule_packs": ["docs.json"],
            "a": FILE_RULE,
        },
    )

    # No warning either: an unexpected one fails the test.
    assert list(_load(_loader([pack]))) == ["a"]


@pytest.mark.parametrize(
    ("content", "reason"),
    [("{not json", "is not valid JSON"), ("[]", "must be a JSON object")],
)
def test_file_that_cannot_be_read_as_rules_stops_with_an_error_naming_it(
    tmp_path: Path, content: str, reason: str
) -> None:
    pack = write_text(tmp_path / "pack.json", content)

    with pytest.raises(ValueError, match=rf"pack\.json' {reason}"):
        _load(_loader([pack]))


def test_target_unit_types_default_to_file_and_explicit_ones_are_kept(
    tmp_path: Path,
) -> None:
    pack = write_json(tmp_path / "pack.json", {"a": FILE_RULE, "b": DIR_RULE})
    rules = _load(_loader([pack]))
    assert rules["a"].target_unit_types == ["file"]
    assert rules["b"].target_unit_types == ["project_directory"]


def test_unknown_target_unit_type_is_rejected(tmp_path: Path) -> None:
    pack = write_json(
        tmp_path / "pack.json", {"a": {**FILE_RULE, "target_unit_types": ["nope"]}}
    )
    with pytest.raises(ValueError, match="unknown target_unit_types"):
        _load(_loader([pack]))


def test_unknown_question_type_is_rejected(tmp_path: Path) -> None:
    pack = write_json(tmp_path / "pack.json", {"a": {**FILE_RULE, "type": "essay"}})
    with pytest.raises(ValueError, match="essay"):
        _load(_loader([pack]))


@pytest.mark.parametrize(
    ("field_name", "bad_value", "message"),
    [
        ("type", "yesno", "has unknown type 'yesno'"),
        ("type", 1, "has unknown type 1"),
        ("target_unit_types", "file", "has invalid target_unit_types 'file'"),
        ("target_unit_types", ["nope"], r"has unknown target_unit_types \['nope'\]"),
        ("instructions", 7, "has invalid instructions 7"),
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
        _load(_loader([pack]))


def test_malformed_rule_in_a_pack_that_is_not_chosen_stops_nothing(
    tmp_path: Path,
) -> None:
    pack = write_json(
        tmp_path / "pack.json",
        _pack(
            {"languages": ["typescript"]},
            {"typo": {"type": "choice"}, "broken": {**FILE_RULE, "type": "yesno"}},
        ),
    )
    loader = _loader([pack])

    # No warning either: an unexpected one fails the test.
    assert _load(loader, PYTHON) == {}
    with (
        pytest.warns(KlintWarning, match="'typo' .* is skipped"),
        pytest.raises(ValueError, match="has unknown type 'yesno'"),
    ):
        _load(loader, TYPESCRIPT)


def test_missing_custom_file_raises(tmp_path: Path) -> None:
    pack = write_json(tmp_path / "pack.json", {"a": FILE_RULE})

    with pytest.raises(FileNotFoundError, match="Custom rules file does not exist"):
        _load(_loader([pack]), custom=tmp_path / "absent.json")


def test_missing_pack_gives_no_rules(tmp_path: Path) -> None:
    absent = tmp_path / "absent.json"
    assert _load(_loader([absent])) == {}
    assert _load(_loader([], [absent]), UNIDENTIFIED) == {}


def test_several_packs_are_merged_in_order(tmp_path: Path) -> None:
    first = write_json(
        tmp_path / "first.json",
        {"shared": {**FILE_RULE, "instructions": "From first?"}, "a": FILE_RULE},
    )
    second = write_json(
        tmp_path / "second.json",
        {"shared": {**FILE_RULE, "instructions": "From second?"}, "b": FILE_RULE},
    )

    rules = _load(_loader([first, second]))

    assert list(rules) == ["shared", "a", "b"]
    assert rules["shared"].instructions == "From second?"


def test_missing_pack_is_skipped_among_several(tmp_path: Path) -> None:
    present = write_json(tmp_path / "present.json", {"a": FILE_RULE})

    rules = _load(_loader([tmp_path / "absent.json", present]))

    assert list(rules) == ["a"]


def test_languages_and_tags_are_read_from_a_rule(tmp_path: Path) -> None:
    pack = write_json(
        tmp_path / "pack.json",
        {
            "scoped": {**FILE_RULE, "languages": ["python"], "tags": ["security"]},
            "plain": FILE_RULE,
            "empty": {**FILE_RULE, "languages": [], "tags": []},
        },
    )

    rules = _load(_loader([pack]))

    assert rules["scoped"].languages == ["python"]
    assert rules["scoped"].tags == ["security"]
    assert (rules["plain"].languages, rules["plain"].tags) == ([], [])
    assert (rules["empty"].languages, rules["empty"].tags) == ([], [])
    assert rules["plain"].target_unit_types == ["file"]


@pytest.mark.parametrize("field_name", ["languages", "tags"])
@pytest.mark.parametrize("bad_value", ["python", ["python", 3], {"a": 1}, None])
def test_malformed_languages_or_tags_are_rejected(
    tmp_path: Path, field_name: str, bad_value: object
) -> None:
    pack = write_json(
        tmp_path / "pack.json", {"broken": {**FILE_RULE, field_name: bad_value}}
    )
    with pytest.raises(ValueError, match=f"Rule 'broken' has invalid {field_name}"):
        _load(_loader([pack]))


def test_built_in_python_project_rules_are_limited_to_python() -> None:
    rules = _load(_loader([PYTHON_PROJECT_RULE_PACK], (), KNOWN_LANGUAGES), PYTHON)

    assert rules
    assert all(rule.languages == ["python"] for rule in rules.values())


def test_built_in_react_rules_are_limited_to_typescript_and_javascript() -> None:
    rules = _load(_loader([REACT_RULE_PACK], (), KNOWN_LANGUAGES), TYPESCRIPT)

    assert rules
    assert all(
        rule.languages == ["typescript", "javascript"] for rule in rules.values()
    )


def test_built_in_rules_set_no_tags() -> None:
    loader = _built_in_loader()
    rules = {**_load(loader, PYTHON), **_load(loader, TYPESCRIPT)}

    assert all(rule.tags == [] for rule in rules.values())


def test_rule_loading_only_accepts_registered_unit_types(tmp_path: Path) -> None:
    pack = write_json(
        tmp_path / "pack.json", {"a": {**FILE_RULE, "target_unit_types": ["file"]}}
    )
    loader = JsonRuleLoader([pack], [], UnitRegistry(), TEST_PACK_LANGUAGES)

    with pytest.raises(ValueError, match="unknown target_unit_types"):
        asyncio.run(loader.load_rules(PYTHON))
