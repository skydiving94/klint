import asyncio
import os
from dataclasses import replace

# Silence Hugging Face Hub & Xet download/reconstruction progress bars before
# importing kev
os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")
os.environ.setdefault("TQDM_DISABLE", "1")

import torch
from huggingface_hub.utils import disable_progress_bars
from kev.checkpoint import Checkpoint, LoadOptions, fused_available
from kev.device import default_device
from kev.serve import Server

from klint.core.interfaces.judge import BaseJudge
from klint.core.models.judge_exchange import JudgeAnswer, JudgeRequest
from klint.infra.system_one.system_one_format import (
    build_system_one_questions,
    read_system_one_answers,
)

disable_progress_bars()


class LocalKevJudge(BaseJudge):
    def __init__(self, checkpoint: str) -> None:
        self._checkpoint = checkpoint
        self._server: Server | None = None
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

    async def answer(self, request: JudgeRequest) -> list[JudgeAnswer]:
        async with self._lock:
            if self._server is None:
                await asyncio.to_thread(self._load_server_sync)

        from kev.api import SystemOneRequest

        system_one_request = SystemOneRequest(
            model=self._checkpoint,
            state=request.subject,
            questions=build_system_one_questions(request),
        )
        assert self._server is not None
        response: object = await self._server.answer_async(system_one_request)
        return read_system_one_answers(response)
