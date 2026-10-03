"""Questions sent to the judge, findings built from answers, and the HTTP client."""

import asyncio
import io
import json
import urllib.request
from pathlib import Path

import pytest

from src.catalog.common.scales.pass_fail import PASS_FAIL_SCALE
from src.core.interfaces.judge import BaseJudge
from src.core.models.location import Location
from src.core.models.report import AuditFinding
from src.core.models.scale import Choice
from src.infra.system_one.remote import RemoteSystemOneJudge
from tests.helpers import (
    FAIL,
    IRRELEVANT,
    LACK_OF_EVIDENCE,
    PASS,
    Answers,
    FakeJudge,
    file_auditor,
    write_json,
)

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


# --- questions -------------------------------------------------------------


def test_unit_content_is_sent_as_state_with_one_question_per_rule(
    fake_judge: type[FakeJudge], target: Path
) -> None:
    judge = fake_judge()

    _findings(judge, target)

    ((state, questions),) = judge.calls
    assert state == "x = 1\n"
    assert questions == {
        rule_id: {
            "type": "choice",
            "instructions": spec["instructions"],
            "criteria": PASS_FAIL_SCALE.criteria_payload(),
        }
        for rule_id, spec in RULES.items()
    }


# --- answers ---------------------------------------------------------------


@pytest.mark.parametrize(
    ("key", "choice"),
    [
        ("pass", PASS),
        ("fail", FAIL),
        ("irrelevant", IRRELEVANT),
        ("lack_of_evidence", LACK_OF_EVIDENCE),
    ],
)
def test_each_answer_maps_to_its_choice(
    fake_judge: type[FakeJudge], target: Path, key: str, choice: Choice
) -> None:
    findings = _findings(fake_judge(default=key), target)
    assert [f.choice for f in findings] == [choice, choice]


def test_finding_carries_the_answer_and_the_unit_location(
    fake_judge: type[FakeJudge], target: Path
) -> None:
    judge = fake_judge(choices={"first": "fail"}, confidence=0.75)

    first, second = _findings(judge, target)

    assert first == AuditFinding(
        rule_id="first",
        unit_id=str(target),
        choice=FAIL,
        instructions="Is the first thing done?",
        confidence=0.75,
        probabilities={"fail": 0.75},
        location=Location(str(target), 1, 1),
        metadata={"file_path": str(target), "line_range": [1, 1]},
    )
    assert second.rule_id == "second"
    assert second.choice is PASS


def test_rule_without_an_answer_produces_no_finding(
    fake_judge: type[FakeJudge], target: Path
) -> None:
    findings = _findings(fake_judge(choices={"first": None}), target)
    assert [f.rule_id for f in findings] == ["second"]


def test_unknown_answer_raises_key_error(
    fake_judge: type[FakeJudge], target: Path
) -> None:
    with pytest.raises(KeyError, match="maybe"):
        _findings(fake_judge(default="maybe"), target)


# --- HTTP transport --------------------------------------------------------


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
