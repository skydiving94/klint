"""Test doubles that stand in for the model and for rule sources."""

import asyncio

from injector import Module, provider, singleton

from klint.core.interfaces.judge import BaseJudge
from klint.core.interfaces.rule_source import BaseRuleSource
from klint.core.models.judge_exchange import JudgeAnswer, JudgeRequest
from klint.core.models.rule_pack import RulePackSpec


class FakeJudge(BaseJudge):
    """Stands in for the model: answers from canned choices, records each request."""

    def __init__(
        self,
        choices: dict[str, str | None] | None = None,
        default: str | None = "pass",
        confidence: float = 0.9,
        rule_id_to_confidence: dict[str, float] | None = None,
    ) -> None:
        """Answer ``choices[rule_id]`` per rule, else ``default``.

        A choice of ``None`` means the model returned no answer for that rule.
        Each answer has the confidence ``rule_id_to_confidence`` gives its
        rule, else ``confidence``.
        """
        self.choices: dict[str, str | None] = choices or {}
        self.default = default
        self.confidence = confidence
        self.rule_id_to_confidence = rule_id_to_confidence or {}
        self.requests: list[JudgeRequest] = []

    async def answer(self, request: JudgeRequest) -> list[JudgeAnswer]:
        self.requests.append(request)
        answers: list[JudgeAnswer] = []
        for question in request.questions:
            choice = self.choices.get(question.question_id, self.default)
            if choice is None:
                continue
            confidence = self.rule_id_to_confidence.get(
                question.question_id, self.confidence
            )
            answers.append(
                JudgeAnswer(
                    question_id=question.question_id,
                    choice_key=choice,
                    confidence=confidence,
                    choice_key_to_probability={choice: confidence},
                )
            )
        return answers

    def asked_rule_ids(self) -> list[list[str]]:
        """Return the rule ids asked in each request, sorted, in request order."""
        return [
            sorted(question.question_id for question in request.questions)
            for request in self.requests
        ]

    def subject_to_asked_rule_ids(self) -> dict[str, set[str]]:
        """Return the rule ids asked about each subject.

        Meant for tests whose subjects all differ: a later request about the
        same subject replaces an earlier one.
        """
        return {
            request.subject: {question.question_id for question in request.questions}
            for request in self.requests
        }


class PickyJudge(FakeJudge):
    """Fails on content that contains ``refuses``; answers "fail" otherwise."""

    def __init__(self, refuses: str) -> None:
        super().__init__(default="fail")
        self.refuses = refuses

    async def answer(self, request: JudgeRequest) -> list[JudgeAnswer]:
        if self.refuses in request.subject:
            raise RuntimeError("judge is down")
        return await super().answer(request)


class CountingJudge(FakeJudge):
    """Records how many requests are being answered at the same time."""

    def __init__(self) -> None:
        super().__init__()
        self.running = 0
        self.most_at_once = 0

    async def answer(self, request: JudgeRequest) -> list[JudgeAnswer]:
        self.running += 1
        self.most_at_once = max(self.most_at_once, self.running)
        await asyncio.sleep(0)
        self.running -= 1
        return await super().answer(request)


class JudgeOverride(Module):
    """Replaces the judge klint would build with the one a test supplies."""

    def __init__(self, judge: BaseJudge) -> None:
        self._judge = judge

    @singleton
    @provider
    def provide_judge(self) -> BaseJudge:
        return self._judge


class InMemoryRuleSource(BaseRuleSource):
    """Holds rule packs built in test code; no file is read."""

    def __init__(self, *packs: RulePackSpec) -> None:
        self._packs = list(packs)

    def read_rule_packs(self) -> list[RulePackSpec]:
        return list(self._packs)
