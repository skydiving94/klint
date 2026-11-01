"""Which units a rule applies to: unit type first, then language and unit tags."""

import pytest

from klint.catalog.code.python.units.package_unit import AuditablePythonPackageUnit
from klint.catalog.domain_neutral.units.file import AuditableFileUnit
from klint.core.models.question_type import QuestionType
from klint.core.models.rule import AuditRule
from klint.core.models.unit_traits import UnitTraits


def _rule(
    languages: list[str] | None = None,
    tags: list[str] | None = None,
    unit_tags: list[str] | None = None,
) -> AuditRule:
    return AuditRule(
        rule_id="r",
        question_type=QuestionType.CHOICE,
        instructions="?",
        languages=languages or [],
        tags=tags or [],
        unit_tags=unit_tags or [],
    )


def _file(
    language: str | None, unit_tags: frozenset[str] = frozenset()
) -> AuditableFileUnit:
    return AuditableFileUnit(
        unit_id="a", traits=UnitTraits(language=language, tags=unit_tags)
    )


def test_new_rule_has_no_languages_or_tags() -> None:
    rule = AuditRule("r", QuestionType.CHOICE, "?")
    assert rule.languages == []
    assert rule.tags == []


@pytest.mark.parametrize("language", [None, "python", "english"])
def test_rule_without_languages_applies_whatever_the_unit_language(
    language: str | None,
) -> None:
    assert _rule().is_applicable_to(_file(language))


def test_rule_with_languages_applies_only_to_those_languages() -> None:
    rule = _rule(languages=["python", "typescript"])
    assert rule.is_applicable_to(_file("python"))
    assert rule.is_applicable_to(_file("typescript"))
    assert not rule.is_applicable_to(_file("go"))


def test_rule_with_languages_does_not_apply_to_an_unknown_language() -> None:
    assert not _rule(languages=["python"]).is_applicable_to(_file(None))


@pytest.mark.parametrize(
    ("rule_language", "unit_language"),
    [("Python", "python"), ("python", "PYTHON"), ("TypeScript", "typescript")],
)
def test_language_names_are_compared_without_regard_to_case(
    rule_language: str, unit_language: str
) -> None:
    assert _rule(languages=[rule_language]).is_applicable_to(_file(unit_language))


def test_unit_type_is_checked_before_language() -> None:
    directory = AuditablePythonPackageUnit(
        unit_id="d", traits=UnitTraits(language="python")
    )
    assert not _rule(languages=["python"]).is_applicable_to(directory)


def test_tags_do_not_affect_which_units_a_rule_applies_to() -> None:
    tagged = _rule(tags=["security", "backend"])
    assert tagged.tags == ["security", "backend"]
    assert tagged.is_applicable_to(_file(None))
    assert tagged.is_applicable_to(_file("python"))


def test_rule_applies_only_to_its_target_unit_types() -> None:
    unit = AuditableFileUnit(unit_id="a.py", content="x = 1")
    file_rule = AuditRule("r", QuestionType.CHOICE, "?")
    dir_rule = AuditRule("r", QuestionType.CHOICE, "?", ["project_directory"])
    assert file_rule.is_applicable_to(unit)
    assert not dir_rule.is_applicable_to(unit)


@pytest.mark.parametrize(
    "unit_tags",
    [frozenset({"backend"}), frozenset({"backend", "frontend"}), frozenset()],
)
def test_rule_limited_to_unit_tags_applies_to_a_unit_with_any_or_none(
    unit_tags: frozenset[str],
) -> None:
    assert _rule(unit_tags=["backend", "cli"]).is_applicable_to(
        _file("python", unit_tags)
    )


def test_rule_limited_to_unit_tags_does_not_apply_to_a_unit_with_others() -> None:
    assert not _rule(unit_tags=["backend"]).is_applicable_to(
        _file("python", frozenset({"frontend"}))
    )


def test_rule_with_no_unit_tags_applies_to_a_tagged_unit() -> None:
    assert _rule().is_applicable_to(_file("python", frozenset({"frontend"})))


def test_unit_tags_are_compared_without_regard_to_case() -> None:
    assert _rule(unit_tags=["Backend"]).is_applicable_to(
        _file(None, frozenset({"backend"}))
    )


def test_rule_unit_tags_and_languages_must_both_allow_the_unit() -> None:
    rule = _rule(languages=["python"], unit_tags=["backend"])

    assert not rule.is_applicable_to(_file("go", frozenset({"backend"})))
    assert not rule.is_applicable_to(_file("python", frozenset({"frontend"})))
