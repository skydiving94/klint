"""The HTTP judge: what is sent to the System One endpoint and what comes back."""

import asyncio
import io
import json
import urllib.request

import pytest

from klint.infra.system_one.remote import RemoteSystemOneJudge
from tests.support.fakes import Answers

STATE = "x = 1\n"
QUESTIONS = {
    "first": {"type": "choice", "instructions": "Is the first thing done?"},
    "second": {"type": "choice", "instructions": "Is the second thing done?"},
}


class FakeEndpoint:
    """Replaces ``urllib.request.urlopen`` and records what was sent."""

    def __init__(self, answers: Answers) -> None:
        self.answers = answers
        self.requests: list[urllib.request.Request] = []
        self.timeouts: list[float] = []

    def __call__(self, request: urllib.request.Request, timeout: float) -> io.BytesIO:
        self.requests.append(request)
        self.timeouts.append(timeout)
        return io.BytesIO(json.dumps({"answers": self.answers}).encode("utf-8"))


def test_request_is_posted_to_the_systemone_endpoint(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    endpoint = FakeEndpoint({"first": {"choice": "fail", "confidence": 0.6}})
    monkeypatch.setattr(urllib.request, "urlopen", endpoint)
    judge = RemoteSystemOneJudge(
        model_name="kev-latest",
        base_url="http://judge.test:8009/",
        api_key="secret",
        timeout_seconds=12.0,
    )

    answers = asyncio.run(judge.answer(STATE, QUESTIONS))

    (request,) = endpoint.requests
    assert request.full_url == "http://judge.test:8009/v1/systemone"
    assert request.get_method() == "POST"
    assert request.get_header("Content-type") == "application/json"
    assert request.get_header("Authorization") == "Bearer secret"
    assert endpoint.timeouts == [12.0]
    assert isinstance(request.data, bytes)
    assert json.loads(request.data) == {
        "model": "kev-latest",
        "state": STATE,
        "questions": QUESTIONS,
    }
    assert answers == {"first": {"choice": "fail", "confidence": 0.6}}


def test_no_authorization_header_without_an_api_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    endpoint = FakeEndpoint({})
    monkeypatch.setattr(urllib.request, "urlopen", endpoint)
    judge = RemoteSystemOneJudge(model_name="kev-latest")

    answers = asyncio.run(judge.answer(STATE, QUESTIONS))

    (request,) = endpoint.requests
    assert request.full_url == "http://127.0.0.1:8009/v1/systemone"
    assert request.get_header("Authorization") is None
    assert answers == {}
