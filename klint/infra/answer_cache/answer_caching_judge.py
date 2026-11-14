"""A judge that answers from the cache what another judge answered before."""

import asyncio
import warnings
from collections import defaultdict

from klint.core import KlintWarning
from klint.core.interfaces import BaseJudge
from klint.core.models.judging import (
    JudgeAnswer,
    JudgeQuestion,
    JudgeReply,
    JudgeRequest,
    JudgeUsage,
)
from klint.infra.answer_cache.answer_store import FileAnswerStore, QuestionKeyToAnswer
from klint.infra.answer_cache.request_keys import build_question_key, build_subject_key


class AnswerCachingJudge(BaseJudge):
    """Asks another judge only the questions the cache has no answer to.

    The cache is keyed by the model's version and the subject, then by each
    question with its criteria, so that a change to any of them asks again.
    A question the judge gives no answer to, or a request it fails on, is
    not stored. The same request asked twice in one run is answered once:
    the second waits for the first. A reply made from the cache alone counts
    no request and no input tokens. The model's version is resolved once,
    when first asked; when it cannot be, the cache is not used in this run,
    with a warning, and every request goes to the judge.
    """

    def __init__(self, judge: BaseJudge, store: FileAnswerStore) -> None:
        self._judge = judge
        self._store = store
        self._model_version: str | None = None
        self._is_version_resolved = False
        self._resolving = asyncio.Lock()
        self._subject_key_to_lock: defaultdict[str, asyncio.Lock] = defaultdict(
            asyncio.Lock
        )
        # What this run read or stored, so that a second identical request
        # is answered from memory even where the folder cannot be written.
        self._subject_key_to_answers: dict[str, QuestionKeyToAnswer] = {}

    async def resolve_model_version(self) -> str | None:
        async with self._resolving:
            if not self._is_version_resolved:
                self._model_version = await self._judge.resolve_model_version()
                self._is_version_resolved = True
                if self._model_version is None:
                    warnings.warn(
                        "The answer cache is not used in this run: the judge's "
                        "model version could not be resolved, so a cached "
                        "answer might come from another model",
                        KlintWarning,
                        stacklevel=2,
                    )
        return self._model_version

    async def answer(self, request: JudgeRequest) -> JudgeReply:
        model_version = await self.resolve_model_version()
        if model_version is None:
            return await self._judge.answer(request)
        subject_key = build_subject_key(model_version, request.subject)
        async with self._subject_key_to_lock[subject_key]:
            return await self._answer_under_lock(request, subject_key, model_version)

    async def _answer_under_lock(
        self, request: JudgeRequest, subject_key: str, model_version: str
    ) -> JudgeReply:
        known = self._subject_key_to_answers.get(subject_key)
        if known is None:
            known = self._store.read_answers(subject_key)
            self._subject_key_to_answers[subject_key] = known
        question_keys = [build_question_key(question) for question in request.questions]
        cached_answers = [known[key] for key in question_keys if key in known]
        unanswered = tuple(
            question
            for question, key in zip(request.questions, question_keys, strict=True)
            if key not in known
        )
        usage = JudgeUsage(cached_question_count=len(cached_answers))
        if not unanswered:
            return JudgeReply(answers=tuple(cached_answers), usage=usage)
        reply = await self._judge.answer(
            JudgeRequest(subject=request.subject, questions=unanswered)
        )
        usage = usage.add(
            JudgeUsage(
                request_count=reply.usage.request_count,
                input_token_count=reply.usage.input_token_count,
                asked_question_count=len(unanswered),
            )
        )
        new_answers = _map_question_key_to_answer(unanswered, reply.answers)
        if new_answers:
            known.update(new_answers)
            self._store.write_answers(subject_key, model_version, known)
        return JudgeReply(answers=(*cached_answers, *reply.answers), usage=usage)


def _map_question_key_to_answer(
    questions: tuple[JudgeQuestion, ...], answers: tuple[JudgeAnswer, ...]
) -> QuestionKeyToAnswer:
    """Return each answer the judge gave, by the key of its question."""
    question_id_to_key = {
        question.question_id: build_question_key(question) for question in questions
    }
    return {
        question_id_to_key[answer.question_id]: answer
        for answer in answers
        if answer.question_id in question_id_to_key
    }
