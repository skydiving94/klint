"""Test doubles and repo paths shared by the test modules."""

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

from src.infrastructure.kev.pretrained import PretrainedKevEvaluator

REPO_ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT_DIR = Path(__file__).resolve().parent / "snapshots"
DEFAULT_RULES = REPO_ROOT / "resources" / "default_rules.json"
DEFAULT_PROJECT_RULES = REPO_ROOT / "resources" / "default_project_rules.json"

Questions = dict[str, Any]
Answers = dict[str, Any]
RuleSpec = dict[str, Any]
SnapshotAsserter = Callable[[str, str], None]

FILE_RULE: RuleSpec = {"type": "choice", "instructions": "Is it tidy?"}
DIR_RULE: RuleSpec = {**FILE_RULE, "target_unit_types": ["project_directory"]}


def write_json(path: Path, data: dict[str, Any]) -> Path:
    """Write ``data`` to ``path`` as JSON and return the path."""
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


class FakeJudge:
    """Stands in for the System One model.

    It is a plain ``(state, questions) -> answers`` callable, plugged into the
    real remote evaluator through its ``inference_fn`` hook, so the evaluator's
    own request building and answer mapping still run.
    """

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

    def __call__(self, state: str, questions: Questions) -> Answers:
        self.calls.append((state, questions))
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

    def evaluator(self) -> PretrainedKevEvaluator:
        """Return the real remote evaluator, answering through this fake."""
        return PretrainedKevEvaluator(model_name="fake", inference_fn=self)
