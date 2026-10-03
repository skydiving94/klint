"""Which units a rule applies to: unit type first, then language."""

import pytest

from src.catalog.code.common.units.directory import AuditableProjectDirectoryUnit
from src.catalog.common.units.file import AuditableFileUnit
from src.core.models.question_type import QuestionType
from src.core.models.rule import AuditRule


def _rule(
    languages: list[str] | None = None, tags: list[str] | None = None
) -> AuditRule:
    return AuditRule(
        rule_id="r",
        question_type=QuestionType.CHOICE,
        instructions="?",
        languages=languages or [],
        tags=tags or [],
    )


def _file(language: str | None) -> AuditableFileUnit:
    return AuditableFileUnit(unit_id="a", language=language)


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
    directory = AuditableProjectDirectoryUnit(unit_id="d", language="python")
    assert not _rule(languages=["python"]).is_applicable_to(directory)


def test_tags_do_not_affect_which_units_a_rule_applies_to() -> None:
    tagged = _rule(tags=["security", "backend"])
    assert tagged.tags == ["security", "backend"]
    assert tagged.is_applicable_to(_file(None))
    assert tagged.is_applicable_to(_file("python"))
