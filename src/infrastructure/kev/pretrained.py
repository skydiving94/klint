import json
import urllib.request
from typing import Any, Callable, Dict, Optional

from src.core.domain.enums import Judgment
from src.core.domain.models import AuditableUnit, AuditFinding, AuditRule
from src.core.interfaces.evaluator import BaseKevEvaluator


class PretrainedKevEvaluator(BaseKevEvaluator):
    def __init__(
        self,
        model_name: str,
        base_url: str = "http://127.0.0.1:8009",
        api_key: Optional[str] = None,
        timeout_seconds: float = 60.0,
        inference_fn: Optional[Callable[[str, Dict[str, Any]], str]] = None,
    ):
        self._model_name = model_name
        self._endpoint = f"{base_url.rstrip('/')}/v1/systemone"
        self._api_key = api_key
        self._timeout = timeout_seconds
        self._inference_fn = inference_fn or self._default_inference

    def evaluate(self, unit: AuditableUnit, rule: AuditRule) -> AuditFinding:
        context = self._format_context(unit)
        question_payload = self._build_question_payload(rule)
        raw_answer = self._inference_fn(context, question_payload)

        return AuditFinding(
            rule_id=rule.rule_id,
            unit_id=unit.unit_id,
            judgment=Judgment(raw_answer),
            instructions=rule.instructions,
            file_path=unit.file_path,
            line_range=unit.line_range,
        )

    def _format_context(self, unit: AuditableUnit) -> str:
        if isinstance(unit.content, dict):
            return "\n".join(f"{k}: {v}" for k, v in unit.content.items())
        return unit.content

    def _build_question_payload(self, rule: AuditRule) -> Dict[str, Any]:
        return {
            rule.rule_id: {
                "type": rule.question_type,
                "instructions": rule.instructions,
                "criteria": rule.criteria,
            }
        }

    def _default_inference(self, context: str, question: Dict[str, Any]) -> str:
        rule_id = next(iter(question))
        payload = {
            "model": self._model_name,
            "state": context,
            "questions": question,
        }

        headers = {"Content-Type": "application/json"}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"

        req = urllib.request.Request(
            self._endpoint,
            data=json.dumps(payload).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=self._timeout) as response:
            response_data = json.loads(response.read().decode("utf-8"))

        choice_key = response_data["answers"][rule_id]["choice"]
        criteria = question[rule_id]["criteria"]
        return criteria.get(choice_key, choice_key)
