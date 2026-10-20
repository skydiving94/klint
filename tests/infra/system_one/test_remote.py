"""The HTTP judge: what is sent to the System One endpoint and what comes back."""

import asyncio
import urllib.error

import pytest

from klint.catalog.code.common.practice_scale import PRACTICE_SCALE
from klint.core.models.judge_exchange import JudgeAnswer, JudgeRequest
from klint.infra.system_one.remote import RemoteSystemOneJudge
from tests.support.builders import build_judge_request
from tests.support.stub_system_one_server import StubSystemOneServer

REQUEST = build_judge_request("x = 1\n", "first", "second")


def _ask(
    server: StubSystemOneServer, request: JudgeRequest = REQUEST
) -> list[JudgeAnswer]:
    judge = RemoteSystemOneJudge(model_name="kev-latest", base_url=server.base_url)
    return asyncio.run(judge.answer(request))


def test_request_is_posted_to_the_systemone_endpoint_in_its_format(
    system_one_server: StubSystemOneServer,
) -> None:
    judge = RemoteSystemOneJudge(
        model_name="kev-latest",
        base_url=f"{system_one_server.base_url}/",
        api_key="secret",
    )

    asyncio.run(judge.answer(REQUEST))

    (received,) = system_one_server.received
    assert received.method == "POST"
    assert received.path == "/v1/systemone"
    assert received.headers["Content-Type"] == "application/json"
    assert received.headers["Authorization"] == "Bearer secret"
    # The keys and values System One has always been sent.
    criteria = PRACTICE_SCALE.map_choice_key_to_criterion()
    assert received.body == {
        "model": "kev-latest",
        "state": "x = 1\n",
        "questions": {
            "first": {
                "type": "choice",
                "instructions": "Is first done?",
                "criteria": criteria,
            },
            "second": {
                "type": "choice",
                "instructions": "Is second done?",
                "criteria": criteria,
            },
        },
    }


def test_no_authorization_header_without_an_api_key(
    system_one_server: StubSystemOneServer,
) -> None:
    _ask(system_one_server)

    (received,) = system_one_server.received
    assert "Authorization" not in received.headers


def test_answers_are_read_from_the_response(
    system_one_server: StubSystemOneServer,
) -> None:
    system_one_server.response_body = {
        "answers": {
            "first": {
                "choice": "fail",
                "confidence": 0.6,
                "probabilities": {"fail": 0.6, "pass": 0.4},
            },
            "second": {"choice": "pass"},
        }
    }

    answers = _ask(system_one_server)

    assert answers == [
        JudgeAnswer(
            question_id="first",
            choice_key="fail",
            confidence=0.6,
            choice_key_to_probability={"fail": 0.6, "pass": 0.4},
        ),
        JudgeAnswer(question_id="second", choice_key="pass"),
    ]


@pytest.mark.parametrize(
    "response_body",
    [
        {},
        {"answers": {}},
        {"answers": {"first": {}}},
        {"answers": {"first": {"choice": None}}},
    ],
)
def test_answer_that_names_no_choice_is_left_out(
    system_one_server: StubSystemOneServer, response_body: object
) -> None:
    system_one_server.response_body = response_body

    assert _ask(system_one_server) == []


@pytest.mark.parametrize(
    ("response_body", "message"),
    [
        ([], "response is not a JSON object"),
        ({"answers": []}, "'answers' is not a JSON object"),
        ({"answers": {"first": "fail"}}, "answer to 'first' is not a JSON object"),
        ({"answers": {"first": {"choice": 1}}}, "choice for 'first' is not text"),
        (
            {"answers": {"first": {"choice": "fail", "confidence": "high"}}},
            "confidence for 'first' is not a number",
        ),
        (
            {"answers": {"first": {"choice": "fail", "probabilities": {"fail": None}}}},
            "probability of 'fail' for 'first' is not a number",
        ),
    ],
)
def test_response_not_in_the_systemone_shape_is_an_error(
    system_one_server: StubSystemOneServer, response_body: object, message: str
) -> None:
    system_one_server.response_body = response_body

    with pytest.raises(ValueError, match=message):
        _ask(system_one_server)


def test_endpoint_that_fails_is_an_error(
    system_one_server: StubSystemOneServer,
) -> None:
    system_one_server.response_status = 500

    with pytest.raises(urllib.error.HTTPError, match="HTTP Error 500"):
        _ask(system_one_server)


def test_endpoint_that_does_not_answer_in_time_is_an_error(
    system_one_server: StubSystemOneServer,
) -> None:
    system_one_server.response_delay_seconds = 0.2
    judge = RemoteSystemOneJudge(
        model_name="kev-latest",
        base_url=system_one_server.base_url,
        timeout_seconds=0.05,
    )

    with pytest.raises(TimeoutError):
        asyncio.run(judge.answer(REQUEST))
