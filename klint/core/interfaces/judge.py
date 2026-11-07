from abc import ABC, abstractmethod

from klint.core.models.judge_exchange import JudgeAnswer, JudgeRequest


class BaseJudge(ABC):
    @abstractmethod
    async def answer(self, request: JudgeRequest) -> list[JudgeAnswer]:
        """Answer the questions in ``request`` about its subject.

        A question the judge gives no answer to has no entry in the result.
        """
