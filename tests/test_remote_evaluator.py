"""The remote evaluator: the request it sends and how it maps the answers."""

import asyncio
import io
import json
import urllib.request

import pytest

from src.core.domain.enums import Judgment, QuestionType
from src.core.domain.report import AuditFinding
from src.core.domain.rule import AuditRule
from src.core.domain.units import AuditableFileUnit
from src.infrastructure.kev.pretrained import PretrainedKevEvaluator
from tests.helpers import Answers, FakeJudge

UNIT = AuditableFileUnit(
    unit_id="a.py", content="x = 1\n", file_path="a.py", start_line=1, end_line=1
)
RULES = [
    AuditRule("first", QuestionType.CHOICE, "Is the first thing done?"),
    AuditRule("second", QuestionType.CHOICE, "Is the second thing done?"),
]


def _evaluate(evaluator: PretrainedKevEvaluator) -> list[AuditFinding]:
    return asyncio.run(evaluator.evaluate(UNIT, RULES))


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


# --- request building ------------------------------------------------------


def test_unit_content_is_sent_as_state_with_one_question_per_rule(
    fake_judge: type[FakeJudge],
) -> None:
    judge = fake_judge()

    _evaluate(judge.evaluator())

    ((state, questions),) = judge.calls
    assert state == "x = 1\n"
    assert questions == {
        rule.rule_id: {
            "type": "choice",
            "instructions": rule.instructions,
            "criteria": Judgment.as_criteria_payload(),
        }
        for rule in RULES
    }


# --- answer mapping --------------------------------------------------------


@pytest.mark.parametrize(
    ("choice", "judgment"),
    [
        ("pass", Judgment.PASS),
        ("fail", Judgment.FAIL),
        ("irrelevant", Judgment.IRRELEVANT),
        ("lack_of_evidence", Judgment.LACK_OF_EVIDENCE),
    ],
)
def test_each_choice_maps_to_its_judgment(
    fake_judge: type[FakeJudge], choice: str, judgment: Judgment
) -> None:
    findings = _evaluate(fake_judge(default=choice).evaluator())
    assert [f.judgment for f in findings] == [judgment, judgment]


def test_finding_carries_the_answer_and_the_unit_location(
    fake_judge: type[FakeJudge],
) -> None:
    judge = fake_judge(choices={"first": "fail"}, confidence=0.75)

    first, second = _evaluate(judge.evaluator())

    assert first == AuditFinding(
        rule_id="first",
        unit_id="a.py",
        judgment=Judgment.FAIL,
        instructions="Is the first thing done?",
        confidence=0.75,
        probabilities={"fail": 0.75},
        metadata={"file_path": "a.py", "line_range": [1, 1]},
    )
    assert second.rule_id == "second"
    assert second.judgment is Judgment.PASS


def test_rule_without_an_answer_produces_no_finding(
    fake_judge: type[FakeJudge],
) -> None:
    findings = _evaluate(fake_judge(choices={"first": None}).evaluator())
    assert [f.rule_id for f in findings] == ["second"]


def test_unknown_choice_raises_key_error(fake_judge: type[FakeJudge]) -> None:
    with pytest.raises(KeyError, match="MAYBE"):
        _evaluate(fake_judge(default="maybe").evaluator())


# --- HTTP transport --------------------------------------------------------


def test_request_is_posted_to_the_systemone_endpoint(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    endpoint = FakeEndpoint({"first": {"choice": "fail", "confidence": 0.6}})
    monkeypatch.setattr(urllib.request, "urlopen", endpoint)
    evaluator = PretrainedKevEvaluator(
        model_name="kev-latest",
        base_url="http://judge.test:8009/",
        api_key="secret",
        timeout_seconds=12.0,
    )

    findings = _evaluate(evaluator)

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
    assert [(f.rule_id, f.judgment, f.confidence) for f in findings] == [
        ("first", Judgment.FAIL, 0.6)
    ]


def test_no_authorization_header_without_an_api_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    endpoint = FakeEndpoint({})
    monkeypatch.setattr(urllib.request, "urlopen", endpoint)

    findings = _evaluate(PretrainedKevEvaluator(model_name="kev-latest"))

    (request,) = endpoint.requests
    assert request.full_url == "http://127.0.0.1:8009/v1/systemone"
    assert request.get_header("Authorization") is None
    assert findings == []
