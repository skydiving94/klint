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

    @abstractmethod
    async def resolve_model_version(self) -> str | None:
        """Return what tells this judge's model apart from every other version.

        Two judges with the same version answer the same request alike, so
        an answer one gave can stand for the other's. A name that may move
        to another model, such as an alias, is resolved to the model it
        names now. None when the version cannot be told, as when the judge
        cannot be reached.
        """
