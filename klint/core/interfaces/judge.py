from abc import ABC, abstractmethod

from klint.core.models.judging import JudgeReply, JudgeRequest


class BaseJudge(ABC):
    @abstractmethod
    async def answer(self, request: JudgeRequest) -> JudgeReply:
        """Answer the questions in ``request`` about its subject.

        A question the judge gives no answer to has no entry in the reply's
        answers. The reply's usage counts the request, with the input tokens
        the judge reported for it.
        """
