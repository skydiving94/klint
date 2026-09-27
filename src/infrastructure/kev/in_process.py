import asyncio
from dataclasses import replace
from typing import Any, Dict, List, Optional, Sequence

import torch
from kev.checkpoint import Checkpoint, LoadOptions, fused_available
from kev.device import default_device
from kev.serve import Server

from src.core.domain.enums import Judgment
from src.core.domain.report import AuditFinding
from src.core.domain.rule import AuditRule
from src.core.domain.units import AuditableUnit
from src.core.interfaces.evaluator import BaseKevEvaluator


class InProcessKevEvaluator(BaseKevEvaluator):
    """Loads Kev weights in-process via kev.serve.Server and evaluates rules without HTTP."""

    def __init__(self, checkpoint: str = "jaredpalmer/kev-0.8b"):
        self._checkpoint = checkpoint
        self._server: Optional[Server] = None
        self._lock = asyncio.Lock()

    def _load_server_sync(self) -> None:
        if self._server is not None:
            return
        dev = default_device()
        opts = LoadOptions.from_env()
        if dev == "mps" and opts.attn is None:
            opts = replace(opts, attn="sdpa")
        if dev != "cpu" and opts.dtype is None:
            opts = replace(opts, dtype=torch.bfloat16)
        if dev == "cuda" and opts.cuda_graphs is None:
            opts = replace(opts, cuda_graphs=True)
        if dev == "cuda" and opts.fused is None:
            opts = replace(opts, fused=fused_available())
        if opts.backend is None:
            opts = replace(opts, backend="auto")

        ck = Checkpoint(self._checkpoint)
        tok, model = ck.load(dev, opts)
        self._server = Server(ck, tok, model, dev)

    async def evaluate(
        self, unit: AuditableUnit, rules: Sequence[AuditRule]
    ) -> List[AuditFinding]:
        async with self._lock:
            if self._server is None:
                await asyncio.to_thread(self._load_server_sync)

        from kev.api import SystemOneRequest

        req = SystemOneRequest(
            model=self._checkpoint,
            state=unit.get_content(),
            questions=self._build_questions_payload(rules),
        )
        assert self._server is not None
        response_data = await self._server.answer_async(req)
        raw_answers = response_data.get("answers", {})

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
                    confidence=answer_data.get("confidence"),
                    probabilities=answer_data.get("probabilities"),
                    metadata=unit.get_metadata(),
                )
            )

        return findings

    def _build_questions_payload(self, rules: Sequence[AuditRule]) -> Dict[str, Any]:
        return {
            rule.rule_id: {
                "type": rule.question_type.value,
                "instructions": rule.instructions,
                "criteria": rule.criteria,
            }
            for rule in rules
        }
