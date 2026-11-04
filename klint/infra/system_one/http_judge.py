import asyncio
import json
import urllib.error
import urllib.request
from http import HTTPStatus

from klint.core.interfaces.judge import BaseJudge
from klint.core.models.judge_exchange import JudgeAnswer, JudgeRequest
from klint.infra.system_one.system_one_format import (
    build_system_one_questions,
    read_system_one_answers,
)

_ACCESS_REFUSED_STATUSES = frozenset({HTTPStatus.UNAUTHORIZED, HTTPStatus.FORBIDDEN})


class JudgeAccessRefusedError(PermissionError):
    """The judge's endpoint refused the request: its API key is missing or wrong."""


class HttpSystemOneJudge(BaseJudge):
    """Asks a model served over HTTP, at the System One endpoint."""

    def __init__(
        self,
        model_name: str,
        base_url: str,
        api_key: str | None = None,
        timeout_seconds: float = 60.0,
    ) -> None:
        self._model_name = model_name
        self._endpoint = f"{base_url.rstrip('/')}/v1/systemone"
        self._api_key = api_key
        self._timeout = timeout_seconds

    async def answer(self, request: JudgeRequest) -> list[JudgeAnswer]:
        response = await asyncio.to_thread(self._post, request)
        return read_system_one_answers(response)

    def _post(self, request: JudgeRequest) -> object:
        """Send ``request`` to the endpoint; return the response as read from JSON."""
        payload = {
            "model": self._model_name,
            "state": request.subject,
            "questions": build_system_one_questions(request),
        }
        headers = {"Content-Type": "application/json"}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"
        http_request = urllib.request.Request(
            self._endpoint,
            data=json.dumps(payload).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        try:
            with urllib.request.urlopen(
                http_request, timeout=self._timeout
            ) as response:
                response_data: object = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as error:
            if error.code in _ACCESS_REFUSED_STATUSES:
                raise JudgeAccessRefusedError(self._describe_refusal(error)) from error
            raise
        return response_data

    def _describe_refusal(self, error: urllib.error.HTTPError) -> str:
        """Say why the endpoint refused the request, without the key itself."""
        status = f"HTTP {error.code}: {error.reason}"
        if not self._api_key:
            return (
                f"the judge at {self._endpoint} needs an API key, and none was "
                f"given ({status})"
            )
        return f"the judge at {self._endpoint} did not accept the API key ({status})"
