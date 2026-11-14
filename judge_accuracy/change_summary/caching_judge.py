"""A judge that answers a request asked before from memory."""

import asyncio
import dataclasses
import json

from klint.core.interfaces import BaseJudge
from klint.core.models.judging import JudgeReply, JudgeRequest, JudgeUsage


class CachingJudge(BaseJudge):
    """Asks another judge, one request at a time, and remembers its answers.

    A planted mistake changes one summary of a document; every other unit's
    text stays as it was in the true document, so its request is answered
    from memory instead of being sent again, and its reply counts no
    request in the judge's usage. A request the other judge
    fails on is not remembered. Requests are sent one at a time: a server
    on this machine answers one at a time, and a request waiting behind
    others could run out its timeout and be counted as refused.
    """

    def __init__(self, judge: BaseJudge) -> None:
        self._judge = judge
        self._request_key_to_reply: dict[str, JudgeReply] = {}
        self._asked_request_count = 0
        self._asked_character_count = 0
        self._reused_request_count = 0
        self._sending = asyncio.Lock()

    async def answer(self, request: JudgeRequest) -> JudgeReply:
        key = json.dumps(dataclasses.asdict(request), sort_keys=True, default=str)
        async with self._sending:
            remembered_reply = self._request_key_to_reply.get(key)
            if remembered_reply is not None:
                self._reused_request_count += 1
                return JudgeReply(
                    answers=remembered_reply.answers,
                    usage=JudgeUsage(request_count=0, input_token_count=0),
                )
            self._asked_request_count += 1
            self._asked_character_count += len(request.subject)
            reply = await self._judge.answer(request)
        self._request_key_to_reply[key] = reply
        return reply

    async def resolve_model_version(self) -> str | None:
        return await self._judge.resolve_model_version()

    def count_asked_requests(self) -> int:
        """Return how many requests were sent to the other judge."""
        return self._asked_request_count

    def count_asked_characters(self) -> int:
        """Return how many characters of subject the requests sent held."""
        return self._asked_character_count

    def count_reused_requests(self) -> int:
        """Return how many requests were answered from memory."""
        return self._reused_request_count
