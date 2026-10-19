import asyncio
import json
import urllib.request

from klint.core.interfaces.judge import BaseJudge
from klint.core.models.judge_exchange import JudgeAnswer, JudgeRequest
from klint.infra.system_one.system_one_format import (
    build_system_one_questions,
    read_system_one_answers,
)


class RemoteSystemOneJudge(BaseJudge):
    """Asks a model served over HTTP, at the System One endpoint."""

    def __init__(
        self,
        model_name: str,
        base_url: str = "http://127.0.0.1:8009",
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
        with urllib.request.urlopen(http_request, timeout=self._timeout) as response:
            response_data: object = json.loads(response.read().decode("utf-8"))
        return response_data
