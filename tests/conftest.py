"""Shared fixtures: an offline fake judge, snapshot comparison and repo paths."""

import os
import socket
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

import pytest

from src.infrastructure.kev.pretrained import PretrainedKevEvaluator

REPO_ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT_DIR = Path(__file__).resolve().parent / "snapshots"
DEFAULT_RULES = REPO_ROOT / "resources" / "default_rules.json"
DEFAULT_PROJECT_RULES = REPO_ROOT / "resources" / "default_project_rules.json"


class FakeJudge:
    """Stands in for the System One model.

    It is a plain ``(state, questions) -> answers`` function, plugged into the
    real remote evaluator through its ``inference_fn`` hook, so the evaluator's
    own request building and answer mapping still run.
    """

    def __init__(
        self,
        choices: Optional[Dict[str, Optional[str]]] = None,
        default: Optional[str] = "pass",
        confidence: float = 0.9,
    ) -> None:
        self.choices = choices or {}
        self.default = default
        self.confidence = confidence
        self.calls: List[Tuple[str, Dict[str, Any]]] = []

    def __call__(self, state: str, questions: Dict[str, Any]) -> Dict[str, Any]:
        self.calls.append((state, questions))
        answers: Dict[str, Any] = {}
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

    def asked_rule_ids(self) -> List[List[str]]:
        return [sorted(questions) for _, questions in self.calls]

    def evaluator(self) -> PretrainedKevEvaluator:
        return PretrainedKevEvaluator(model_name="fake", inference_fn=self)


@pytest.fixture
def fake_judge() -> Callable[..., FakeJudge]:
    return FakeJudge


@pytest.fixture(autouse=True)
def _no_network(monkeypatch: pytest.MonkeyPatch) -> None:
    """Fail any test that tries to open a network connection."""

    def _blocked(*args: Any, **kwargs: Any) -> None:
        raise RuntimeError("network access is not allowed in tests")

    monkeypatch.setattr(socket.socket, "connect", _blocked)


@pytest.fixture
def in_repo_root(monkeypatch: pytest.MonkeyPatch) -> Path:
    """Run from the repo root so unit ids and paths in output stay relative."""
    monkeypatch.chdir(REPO_ROOT)
    return REPO_ROOT


@pytest.fixture
def assert_snapshot() -> Callable[[str, str], None]:
    """Compare text with tests/snapshots/<name>.

    Set UPDATE_SNAPSHOTS=1 to (re)write the stored file, then review the diff.
    """

    def _assert(name: str, actual: str) -> None:
        path = SNAPSHOT_DIR / name
        if os.environ.get("UPDATE_SNAPSHOTS") == "1":
            path.write_text(actual, encoding="utf-8")
            return
        assert path.is_file(), (
            f"missing snapshot {path}; run with UPDATE_SNAPSHOTS=1 to create it"
        )
        assert actual == path.read_text(encoding="utf-8")

    return _assert
