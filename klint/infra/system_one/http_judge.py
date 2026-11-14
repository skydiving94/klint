import asyncio
import json
import urllib.error
import urllib.request
from http import HTTPStatus

from klint.core.interfaces import BaseJudge
from klint.core.models.judging import JudgeReply, JudgeRequest
from klint.infra.system_one.system_one_format import (
    build_system_one_questions,
    describe_model_version,
    read_system_one_reply,
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
        self._models_endpoint = f"{base_url.rstrip('/')}/v1/models"
        self._api_key = api_key
        self._timeout = timeout_seconds

    async def answer(self, request: JudgeRequest) -> JudgeReply:
        response = await asyncio.to_thread(self._post, request)
        return read_system_one_reply(response)

    async def resolve_model_version(self) -> str | None:
        """Return the version of the model, from the server's list of models.

        The list gives each model name a card; the version is the card of
        this judge's model name, in full, so that a name that moves to a new
        release (a new release date, or a new description) is a new version.
        None when the server cannot be reached or answers with another
        shape.
        """
        try:
            response = await asyncio.to_thread(self._get_models)
        except (OSError, ValueError):
            return None
        return describe_model_version(response, self._model_name)

    def _get_models(self) -> object:
        """Fetch the server's list of models; return it as read from JSON."""
        http_request = urllib.request.Request(
            self._models_endpoint, headers=self._build_headers(), method="GET"
        )
        with urllib.request.urlopen(http_request, timeout=self._timeout) as response:
            response_data: object = json.loads(response.read().decode("utf-8"))
        return response_data

    def _post(self, request: JudgeRequest) -> object:
        """Send ``request`` to the endpoint; return the response as read from JSON."""
        payload = {
            "model": self._model_name,
            "state": request.subject,
            "questions": build_system_one_questions(request),
        }
        http_request = urllib.request.Request(
            self._endpoint,
            data=json.dumps(payload).encode("utf-8"),
            headers=self._build_headers(),
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

    def _build_headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"
        return headers

    def _describe_refusal(self, error: urllib.error.HTTPError) -> str:
        """Say why the endpoint refused the request, without the key itself."""
        status = f"HTTP {error.code}: {error.reason}"
        if not self._api_key:
            return (
                f"the judge at {self._endpoint} needs an API key, and none was "
                f"given ({status})"
            )
        return f"the judge at {self._endpoint} did not accept the API key ({status})"
