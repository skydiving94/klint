import asyncio
import json
import urllib.request
from typing import Any, Callable, Dict, List, Optional, Sequence
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
        inference_fn: Optional[Callable[[
            str, Dict[str, Any]], Dict[str, Any]]] = None,
    ):
        self._model_name = model_name
        self._endpoint = f"{base_url.rstrip('/')}/v1/systemone"
        self._api_key = api_key
        self._timeout = timeout_seconds
        self._inference_fn = inference_fn or self._default_inference

    async def evaluate(
        self, unit: AuditableUnit, rules: Sequence[AuditRule]
    ) -> List[AuditFinding]:
        context = self._format_context(unit)
        questions_payload = self._build_questions_payload(rules)
        raw_answers = await asyncio.to_thread(
            self._inference_fn, context, questions_payload
        )

        findings: List[AuditFinding] = []
        for rule in rules:
            answer_data = raw_answers.get(rule.rule_id, {})
            choice_key = answer_data.get("choice")
            if choice_key is None:
                continue

            mapped_judgment = rule.criteria.get(choice_key, choice_key)
            findings.append(
                AuditFinding(
                    rule_id=rule.rule_id,
                    unit_id=unit.unit_id,
                    judgment=Judgment(mapped_judgment),
                    instructions=rule.instructions,
                    file_path=unit.file_path,
                    line_range=unit.line_range,
                    confidence=answer_data.get("confidence"),
                    probabilities=answer_data.get("probabilities"),
                )
            )

        return findings

    def _format_context(self, unit: AuditableUnit) -> str:
        if isinstance(unit.content, dict):
            return "\n".join(f"{k}: {v}" for k, v in unit.content.items())
        return unit.content

    def _build_questions_payload(self, rules: Sequence[AuditRule]) -> Dict[str, Any]:
        return {
            rule.rule_id: {
                "type": rule.question_type,
                "instructions": rule.instructions,
                "criteria": rule.criteria,
            }
            for rule in rules
        }

    def _default_inference(
        self, context: str, questions: Dict[str, Any]
    ) -> Dict[str, Any]:
        payload = {
            "model": self._model_name,
            "state": context,
            "questions": questions,
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

        return response_data.get("answers", {})
