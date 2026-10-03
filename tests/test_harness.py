"""Checks on the test harness itself."""

import asyncio
import socket
import sys

import pytest

from tests.helpers import DEFAULT_PROJECT_RULES, DEFAULT_RULE_PACKS, FakeJudge


def test_fake_judge_answers_every_question(fake_judge: type[FakeJudge]) -> None:
    judge = fake_judge(choices={"b": "fail", "c": None})
    answers = asyncio.run(judge.answer("some state", {"a": {}, "b": {}, "c": {}}))
    assert answers["a"]["choice"] == "pass"
    assert answers["b"]["choice"] == "fail"
    assert "c" not in answers
    assert judge.asked_rule_ids() == [["a", "b", "c"]]


def test_network_is_blocked() -> None:
    with pytest.raises(RuntimeError, match="network access"):
        socket.create_connection(("127.0.0.1", 9), timeout=0.1)


def test_no_model_runtime_is_loaded() -> None:
    assert "torch" not in sys.modules
    assert "kev" not in sys.modules


def test_default_rule_packs_exist() -> None:
    assert all(pack.is_file() for pack in DEFAULT_RULE_PACKS)
    assert DEFAULT_PROJECT_RULES.is_file()
