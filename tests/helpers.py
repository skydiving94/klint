"""Test doubles and repo paths shared by the test modules."""

import json
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

from src import catalog
from src.catalog.common.scales.pass_fail import PASS_FAIL_SCALE
from src.core.interfaces.judge import BaseJudge
from src.core.registry import UnitRegistry

REPO_ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT_DIR = Path(__file__).resolve().parent / "snapshots"
RULE_PACKS = REPO_ROOT / "src" / "resources" / "catalog" / "code"
# The built-in file-audit packs, in the order klint loads them.
DEFAULT_RULE_PACKS = (
    RULE_PACKS / "common" / "backend.json",
    RULE_PACKS / "typescript" / "react.json",
    RULE_PACKS / "common" / "structure.json",
)
DEFAULT_PROJECT_RULES = RULE_PACKS / "python" / "project_structure.json"

Questions = dict[str, Any]
Answers = dict[str, Any]
RuleSpec = dict[str, Any]
SnapshotAsserter = Callable[[str, str], None]

FILE_RULE: RuleSpec = {"type": "choice", "instructions": "Is it tidy?"}
DIR_RULE: RuleSpec = {**FILE_RULE, "target_unit_types": ["project_directory"]}


def build_unit_registry() -> UnitRegistry:
    """Return a registry holding the unit types of every built-in suite."""
    registry = UnitRegistry()
    catalog.register(registry)
    return registry


UNIT_REGISTRY = build_unit_registry()

# The four answers of the default scale, for building and checking findings.
PASS = PASS_FAIL_SCALE.choice("pass")
FAIL = PASS_FAIL_SCALE.choice("fail")
IRRELEVANT = PASS_FAIL_SCALE.choice("irrelevant")
LACK_OF_EVIDENCE = PASS_FAIL_SCALE.choice("lack_of_evidence")


def write_json(path: Path, data: dict[str, Any]) -> Path:
    """Write ``data`` to ``path`` as JSON and return the path."""
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


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
