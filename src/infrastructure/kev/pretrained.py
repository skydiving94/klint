import asyncio
import json
import urllib.request
from typing import Any, Callable, Dict, List, Optional, Sequence

from src.core.models.judgment import Judgment
from src.core.models.report import AuditFinding
from src.core.models.rule import AuditRule
from src.core.models.units import AuditableUnit
from src.core.interfaces.evaluator import BaseKevEvaluator


class PretrainedKevEvaluator(BaseKevEvaluator):
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

    async def evaluate(self, unit: AuditableUnit, rules: Sequence[AuditRule]) -> List[AuditFinding]:
        context = unit.get_content()
        questions_payload = self._build_questions_payload(rules)
        raw_answers = await asyncio.to_thread(self._inference_fn, context, questions_payload)

        findings: List[AuditFinding] = []
        for rule in rules:
            answer_data = raw_answers.get(rule.rule_id, {})
            choice_key = answer_data.get("choice")
            if choice_key is None:
                continue
            findings.append(
                AuditFinding(
                    rule_id=rule.rule_id,
                    unit_id=unit.unit_id,
                    judgment=Judgment[choice_key.upper()],
                    instructions=rule.instructions,
                    confidence=answer_data.get("confidence"),
                    probabilities=answer_data.get("probabilities"),
                    metadata=unit.get_metadata(),
                )
            )
        return findings

    def _build_questions_payload(self, rules: Sequence[AuditRule]) -> Dict[str, Any]:
        criteria = Judgment.as_criteria_payload()
        return {
            rule.rule_id: {"type": rule.question_type.value,
                           "instructions": rule.instructions, "criteria": criteria}
            for rule in rules
        }

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
