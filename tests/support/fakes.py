"""Test doubles that stand in for the model."""

from collections.abc import Mapping
from typing import Any

from injector import Module, provider, singleton

from src.core.interfaces.judge import BaseJudge

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


class JudgeOverride(Module):
    """Replaces the judge klint would build with the one a test supplies."""

    def __init__(self, judge: BaseJudge) -> None:
        self._judge = judge

    @singleton
    @provider
    def provide_judge(self) -> BaseJudge:
        return self._judge
