import asyncio
import json
import urllib.request
from typing import Any, Callable, Dict, Mapping, Optional

from src.core.interfaces.judge import BaseJudge


class RemoteSystemOneJudge(BaseJudge):
    def __init__(
        self,
        model_name: str,
        base_url: str = "http://127.0.0.1:8009",
        api_key: Optional[str] = None,
        timeout_seconds: float = 60.0,
        inference_fn: Optional[Callable[[
            str, Dict[str, Any]], Dict[str, Any]]] = None,
    ):
        self._model_name = model_name
        self._endpoint = f"{base_url.rstrip('/')}/v1/systemone"
        self._api_key = api_key
        self._timeout = timeout_seconds
        self._inference_fn = inference_fn or self._default_inference

    async def answer(
        self, state: str, questions: Mapping[str, Any]
    ) -> Mapping[str, Any]:
        return await asyncio.to_thread(self._inference_fn, state, dict(questions))

    def _default_inference(self, context: str, questions: Dict[str, Any]) -> Dict[str, Any]:
        payload = {"model": self._model_name,
                   "state": context, "questions": questions}
        headers = {"Content-Type": "application/json"}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"
        req = urllib.request.Request(
            self._endpoint, data=json.dumps(payload).encode("utf-8"), headers=headers, method="POST"
        )
        with urllib.request.urlopen(req, timeout=self._timeout) as response:
            response_data = json.loads(response.read().decode("utf-8"))
        return response_data.get("answers", {})
