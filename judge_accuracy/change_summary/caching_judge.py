"""A judge that answers a request asked before from memory."""

import asyncio
import dataclasses
import json

from klint.core.interfaces import BaseJudge
from klint.core.models.judging import JudgeAnswer, JudgeRequest


class CachingJudge(BaseJudge):
    """Asks another judge, one request at a time, and remembers its answers.

    A planted mistake changes one summary of a document; every other unit's
    text stays as it was in the true document, so its request is answered
    from memory instead of being sent again. A request the other judge
    fails on is not remembered. Requests are sent one at a time: a server
    on this machine answers one at a time, and a request waiting behind
    others could run out its timeout and be counted as refused.
    """

    def __init__(self, judge: BaseJudge) -> None:
        self._judge = judge
        self._request_key_to_answers: dict[str, list[JudgeAnswer]] = {}
        self._asked_request_count = 0
        self._asked_character_count = 0
        self._reused_request_count = 0
        self._sending = asyncio.Lock()

    async def answer(self, request: JudgeRequest) -> list[JudgeAnswer]:
        key = json.dumps(dataclasses.asdict(request), sort_keys=True, default=str)
        async with self._sending:
            answers = self._request_key_to_answers.get(key)
            if answers is not None:
                self._reused_request_count += 1
                return list(answers)
            self._asked_request_count += 1
            self._asked_character_count += len(request.subject)
            answers = await self._judge.answer(request)
        self._request_key_to_answers[key] = list(answers)
        return answers

    def count_asked_requests(self) -> int:
        """Return how many requests were sent to the other judge."""
        return self._asked_request_count

    def count_asked_characters(self) -> int:
        """Return how many characters of subject the requests sent held."""
        return self._asked_character_count

    def count_reused_requests(self) -> int:
        """Return how many requests were answered from memory."""
        return self._reused_request_count
