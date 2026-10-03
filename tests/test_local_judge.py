"""The in-process kev judge, exercised with stand-ins for torch and kev."""

import asyncio
import dataclasses
import importlib
import sys
from collections.abc import Iterator
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

from src.catalog.common.extractors.whole_file import WholeFileExtractor
from src.catalog.common.scales.pass_fail import PASS_FAIL_SCALE
from src.core.auditor import Auditor
from src.core.interfaces.judge import BaseJudge
from src.infra.rule_loader.json_loader import JsonRuleLoader
from tests.helpers import FILE_RULE, UNIT_REGISTRY, write_json

LOCAL_MODULE = "src.infra.system_one.local"


@dataclasses.dataclass(frozen=True)
class FakeLoadOptions:
    attn: str | None = None
    dtype: str | None = None
    cuda_graphs: bool | None = None
    fused: bool | None = None
    backend: str | None = None

    @classmethod
    def from_env(cls) -> "FakeLoadOptions":
        return cls()


@dataclasses.dataclass(frozen=True)
class FakeRequest:
    model: str
    state: str
    questions: dict[str, Any]


class FakeRuntime:
    """Records what the judge asks of kev, and answers "fail" to everything."""

    def __init__(self, device: str) -> None:
        self.device = device
        self.checkpoints: list[str] = []
        self.load_options: list[FakeLoadOptions] = []
        self.requests: list[FakeRequest] = []
        self.response_has_answers = True

    def modules(self) -> dict[str, ModuleType]:
        """Return stand-in modules for everything the local judge imports."""
        runtime = self

        class Checkpoint:
            def __init__(self, name: str) -> None:
                runtime.checkpoints.append(name)

            def load(self, device: str, options: FakeLoadOptions) -> tuple[str, str]:
                runtime.load_options.append(options)
                return (f"tokenizer-for-{device}", "model")

        class Server:
            def __init__(self, *loaded: object) -> None:
                self.loaded = loaded

            async def answer_async(self, request: FakeRequest) -> dict[str, Any]:
                runtime.requests.append(request)
                if not runtime.response_has_answers:
                    return {}
                answers = {rule_id: {"choice": "fail"} for rule_id in request.questions}
                return {"answers": answers}

        return {
            "torch": _module("torch", bfloat16="bfloat16"),
            "huggingface_hub": _module("huggingface_hub"),
            "huggingface_hub.utils": _module(
                "huggingface_hub.utils", disable_progress_bars=lambda: None
            ),
            "kev": _module("kev"),
            "kev.checkpoint": _module(
                "kev.checkpoint",
                Checkpoint=Checkpoint,
                LoadOptions=FakeLoadOptions,
                fused_available=lambda: True,
            ),
            "kev.device": _module("kev.device", default_device=lambda: runtime.device),
            "kev.serve": _module("kev.serve", Server=Server),
            "kev.api": _module("kev.api", SystemOneRequest=FakeRequest),
        }


def _module(name: str, **attributes: object) -> ModuleType:
    module = ModuleType(name)
    module.__dict__.update(attributes)
    return module


@pytest.fixture
def runtime(monkeypatch: pytest.MonkeyPatch) -> Iterator[FakeRuntime]:
    """Install the stand-ins for the duration of one test."""
    fake = FakeRuntime(device="cpu")
    for name, module in fake.modules().items():
        monkeypatch.setitem(sys.modules, name, module)
    # Importing the judge sets these; setting them here lets pytest undo it.
    monkeypatch.setenv("HF_HUB_DISABLE_PROGRESS_BARS", "1")
    monkeypatch.setenv("TQDM_DISABLE", "1")
    sys.modules.pop(LOCAL_MODULE, None)
    yield fake
    sys.modules.pop(LOCAL_MODULE, None)


def _local_judge(checkpoint: str = "org/model") -> BaseJudge:
    judge = importlib.import_module(LOCAL_MODULE).LocalKevJudge(checkpoint=checkpoint)
    assert isinstance(judge, BaseJudge)
    return judge


def test_answer_sends_model_state_and_questions_and_returns_the_answers(
    runtime: FakeRuntime,
) -> None:
    questions = {"rule_a": {"type": "choice"}, "rule_b": {"type": "choice"}}

    answers = asyncio.run(_local_judge().answer("x = 1", questions))

    assert runtime.requests == [FakeRequest("org/model", "x = 1", questions)]
    assert answers == {"rule_a": {"choice": "fail"}, "rule_b": {"choice": "fail"}}


def test_model_is_loaded_once_and_reused(runtime: FakeRuntime) -> None:
    judge = _local_judge()

    async def ask_three_times() -> None:
        await asyncio.gather(*(judge.answer("x", {"r": {}}) for _ in range(3)))

    asyncio.run(ask_three_times())

    assert runtime.checkpoints == ["org/model"]
    assert len(runtime.load_options) == 1
    assert len(runtime.requests) == 3


@pytest.mark.parametrize(
    ("device", "expected"),
    [
        ("cpu", FakeLoadOptions(backend="auto")),
        ("mps", FakeLoadOptions(attn="sdpa", dtype="bfloat16", backend="auto")),
        (
            "cuda",
            FakeLoadOptions(
                dtype="bfloat16", cuda_graphs=True, fused=True, backend="auto"
            ),
        ),
    ],
)
def test_load_options_depend_on_the_device(
    runtime: FakeRuntime, device: str, expected: FakeLoadOptions
) -> None:
    runtime.device = device

    asyncio.run(_local_judge().answer("x", {"r": {}}))

    assert runtime.load_options == [expected]


def test_response_without_answers_gives_no_answers(runtime: FakeRuntime) -> None:
    runtime.response_has_answers = False
    assert asyncio.run(_local_judge().answer("x", {"r": {}})) == {}


@pytest.mark.usefixtures("runtime")
def test_auditor_turns_local_judge_answers_into_findings(tmp_path: Path) -> None:
    rules = write_json(tmp_path / "rules.json", {"tidy": FILE_RULE})
    target = tmp_path / "a.py"
    target.write_text("x = 1\n", encoding="utf-8")
    auditor = Auditor(
        extractor=WholeFileExtractor(),
        judge=_local_judge(),
        rule_loader=JsonRuleLoader([rules], UNIT_REGISTRY),
        scale=PASS_FAIL_SCALE,
    )

    (issue,) = asyncio.run(auditor.run_audit(target)).get_issues()

    assert (issue["rule_id"], issue["judgment"]) == ("tidy", "Fail")
