"""The HTTP judge: what is sent to the System One endpoint and what comes back."""

import asyncio
import io
import json
import urllib.request
from pathlib import Path

import pytest

from src.core.interfaces.judge import BaseJudge
from src.core.models.report import AuditFinding
from src.infra.system_one.remote import RemoteSystemOneJudge
from tests.support.builders import FAIL, file_auditor, write_json
from tests.support.fakes import Answers

RULES = {
    "first": {"type": "choice", "instructions": "Is the first thing done?"},
    "second": {"type": "choice", "instructions": "Is the second thing done?"},
}


@pytest.fixture
def target(tmp_path: Path) -> Path:
    path = tmp_path / "a.py"
    path.write_text("x = 1\n", encoding="utf-8")
    return path


def _findings(judge: BaseJudge, target: Path) -> list[AuditFinding]:
    """Audit ``target`` against RULES and return every finding."""
    rules_path = write_json(target.parent / "rules.json", RULES)
    auditor = file_auditor(rules_path, judge)
    return asyncio.run(auditor.run_audit(target)).get_findings(fails_only=False)


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
    monkeypatch: pytest.MonkeyPatch, target: Path
) -> None:
    endpoint = FakeEndpoint({"first": {"choice": "fail", "confidence": 0.6}})
    monkeypatch.setattr(urllib.request, "urlopen", endpoint)
    judge = RemoteSystemOneJudge(
        model_name="kev-latest",
        base_url="http://judge.test:8009/",
        api_key="secret",
        timeout_seconds=12.0,
    )

    findings = _findings(judge, target)

    (request,) = endpoint.requests
    assert request.full_url == "http://judge.test:8009/v1/systemone"
    assert request.get_method() == "POST"
    assert request.get_header("Content-type") == "application/json"
    assert request.get_header("Authorization") == "Bearer secret"
    assert endpoint.timeouts == [12.0]
    assert isinstance(request.data, bytes)
    body = json.loads(request.data)
    assert body["model"] == "kev-latest"
    assert body["state"] == "x = 1\n"
    assert sorted(body["questions"]) == ["first", "second"]
    assert [(f.rule_id, f.choice, f.confidence) for f in findings] == [
        ("first", FAIL, 0.6)
    ]


def test_no_authorization_header_without_an_api_key(
    monkeypatch: pytest.MonkeyPatch, target: Path
) -> None:
    endpoint = FakeEndpoint({})
    monkeypatch.setattr(urllib.request, "urlopen", endpoint)

    findings = _findings(RemoteSystemOneJudge(model_name="kev-latest"), target)

    (request,) = endpoint.requests
    assert request.full_url == "http://127.0.0.1:8009/v1/systemone"
    assert request.get_header("Authorization") is None
    assert findings == []
