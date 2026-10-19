"""Checks on the test harness itself."""

import asyncio
import socket
import sys

import pytest

from klint.core.models.judge_exchange import JudgeAnswer
from tests.support.builders import build_judge_request
from tests.support.fakes import FakeJudge
from tests.support.paths import BUILT_IN_RULE_PACKS, FALLBACK_RULE_PACKS


def test_fake_judge_answers_every_question(fake_judge: type[FakeJudge]) -> None:
    judge = fake_judge(choices={"b": "fail", "c": None}, confidence=0.7)
    answers = asyncio.run(
        judge.answer(build_judge_request("some state", "a", "b", "c"))
    )
    assert answers == [
        JudgeAnswer("a", "pass", 0.7, {"pass": 0.7}),
        JudgeAnswer("b", "fail", 0.7, {"fail": 0.7}),
    ]
    assert judge.asked_rule_ids() == [["a", "b", "c"]]


def test_network_is_blocked() -> None:
    with pytest.raises(RuntimeError, match="network access"):
        socket.create_connection(("127.0.0.1", 9), timeout=0.1)


def test_no_model_runtime_is_loaded() -> None:
    assert "torch" not in sys.modules
    assert "kev" not in sys.modules


def test_built_in_rule_packs_exist() -> None:
    assert all(pack.is_file() for pack in BUILT_IN_RULE_PACKS)
    assert set(FALLBACK_RULE_PACKS) <= set(BUILT_IN_RULE_PACKS)
