"""Answer scales: looking up a choice and defining a new scale."""

import pytest

from src.catalog.common.scales.pass_fail import PASS_FAIL_SCALE
from src.core.models.scale import AnswerScale, Choice


def test_choice_lookup_ignores_case_and_rejects_unknown_keys() -> None:
    assert PASS_FAIL_SCALE.choice("FAIL") is PASS_FAIL_SCALE.choice("fail")
    with pytest.raises(KeyError, match="maybe"):
        PASS_FAIL_SCALE.choice("maybe")


def test_a_suite_can_define_its_own_scale() -> None:
    rubric = AnswerScale(
        name="rubric",
        choices=(
            Choice("strong", "Strong", "The essay argues its thesis clearly."),
            Choice("weak", "Weak", "The essay does not.", is_finding=True),
        ),
    )
    assert list(rubric.criteria_payload()) == ["strong", "weak"]
    assert rubric.choice("weak").is_finding
