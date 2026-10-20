"""Answer scales: looking up a choice and defining a new scale."""

import pytest

from klint.catalog.code.common.practice_scale import PRACTICE_SCALE
from klint.core.models.scale import AnswerChoice, AnswerScale


def test_choice_lookup_ignores_case_and_rejects_unknown_keys() -> None:
    assert PRACTICE_SCALE.find_choice("FAIL") == PRACTICE_SCALE.find_choice("fail")
    with pytest.raises(KeyError, match="maybe"):
        PRACTICE_SCALE.find_choice("maybe")


def test_a_suite_can_define_its_own_scale() -> None:
    rubric = AnswerScale(
        name="rubric",
        choices=(
            AnswerChoice("strong", "Strong", "The essay argues its thesis clearly."),
            AnswerChoice("weak", "Weak", "The essay does not.", is_problem=True),
        ),
    )
    assert list(rubric.map_choice_key_to_criterion()) == ["strong", "weak"]
    assert rubric.find_choice("weak").is_problem
