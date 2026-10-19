"""Test doubles that stand in for the model."""

import asyncio
from collections.abc import Mapping
from typing import Any

from injector import Module, provider, singleton

from klint.core.interfaces.judge import BaseJudge

Questions = dict[str, Any]
Answers = dict[str, Any]


class FakeJudge(BaseJudge):
    """Stands in for the model: answers from canned choices and records every call."""

    def __init__(
        self,
        choices: dict[str, str | None] | None = None,
        default: str | None = "pass",
        confidence: float = 0.9,
    ) -> None:
        """Answer ``choices[rule_id]`` per rule, else ``default``.

        A choice of ``None`` means the model returned no answer for that rule.
        """
        self.choices: dict[str, str | None] = choices or {}
        self.default = default
        self.confidence = confidence
        self.calls: list[tuple[str, Questions]] = []

    async def answer(self, state: str, questions: Mapping[str, Any]) -> Answers:
        self.calls.append((state, dict(questions)))
        answers: Answers = {}
        for rule_id in questions:
            choice = self.choices.get(rule_id, self.default)
            if choice is None:
                continue
            answers[rule_id] = {
                "choice": choice,
                "confidence": self.confidence,
                "probabilities": {choice: self.confidence},
            }
        return answers

    def asked_rule_ids(self) -> list[list[str]]:
        """Return the rule ids asked in each call, in call order."""
        return [sorted(questions) for _, questions in self.calls]


class PickyJudge(FakeJudge):
    """Fails on content that contains ``refuses``; answers "fail" otherwise."""

    def __init__(self, refuses: str) -> None:
        super().__init__(default="fail")
        self.refuses = refuses

    async def answer(self, state: str, questions: Mapping[str, Any]) -> Answers:
        if self.refuses in state:
            raise RuntimeError("judge is down")
        return await super().answer(state, questions)


class CountingJudge(FakeJudge):
    """Records how many questions are being answered at the same time."""

    def __init__(self) -> None:
        super().__init__()
        self.running = 0
        self.most_at_once = 0

    async def answer(self, state: str, questions: Mapping[str, Any]) -> Answers:
        self.running += 1
        self.most_at_once = max(self.most_at_once, self.running)
        await asyncio.sleep(0)
        self.running -= 1
        return await super().answer(state, questions)


class JudgeOverride(Module):
    """Replaces the judge klint would build with the one a test supplies."""

    def __init__(self, judge: BaseJudge) -> None:
        self._judge = judge

    @singleton
    @provider
    def provide_judge(self) -> BaseJudge:
        return self._judge
