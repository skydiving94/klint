"""Feeding SessionStart and Stop events to klint's stop hook, and reading its answer."""

import asyncio
import json
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from klint.cli import ChangeSummaryStopHook
from klint.cli.change_summary_stop_hook import SUMMARIES_PATH
from klint.core.interfaces import BaseJudge
from tests.support.change_summary import HypothesisJudge
from tests.support.fakes import JudgeBindingOverride
from tests.support.git_summaries import GREETER_SUMMARIES


@dataclass(frozen=True)
class HookAnswer:
    """What the hook printed: a block and its reason, or a warning, or nothing.

    output is the printed text itself.
    """

    output: str
    is_block: bool
    reason: str | None
    warning: str | None

    def is_plain_stop(self) -> bool:
        """Return True when the hook lets the agent stop and says nothing."""
        return self.output == ""


def feed_stop_event(
    project: Path,
    judge: BaseJudge,
    *,
    session_id: str = "session-1",
    is_stop_hook_active: bool = False,
    options: Sequence[str] = (),
) -> HookAnswer:
    """Feed the hook a Stop event of ``project``; return what it printed.

    ``judge`` stands in for the model.
    """
    event = {
        "session_id": session_id,
        "transcript_path": str(project / "transcript.jsonl"),
        "cwd": str(project),
        "permission_mode": "default",
        "hook_event_name": "Stop",
        "stop_hook_active": is_stop_hook_active,
    }
    hook = ChangeSummaryStopHook(JudgeBindingOverride(judge))
    output = asyncio.run(hook.respond(list(options), json.dumps(event)))
    return read_hook_answer(output)


def feed_session_start_event(
    project: Path, *, session_id: str = "session-1", source: str = "startup"
) -> str:
    """Feed the hook a SessionStart event of ``project``; return what it printed."""
    event = {
        "session_id": session_id,
        "transcript_path": str(project / "transcript.jsonl"),
        "cwd": str(project),
        "permission_mode": "default",
        "hook_event_name": "SessionStart",
        "source": source,
    }
    hook = ChangeSummaryStopHook(JudgeBindingOverride(HypothesisJudge()))
    return asyncio.run(hook.respond([], json.dumps(event)))


def read_hook_answer(output: str) -> HookAnswer:
    """Return the answer ``output``, what the hook printed, holds."""
    if not output:
        return HookAnswer(output, is_block=False, reason=None, warning=None)
    fields = json.loads(output)
    return HookAnswer(
        output,
        is_block=fields.get("decision") == "block",
        reason=fields.get("reason"),
        warning=fields.get("systemMessage"),
    )


def write_summaries(project: Path, summaries: object = GREETER_SUMMARIES) -> Path:
    """Write ``summaries`` as JSON where the hook reads them; return the path."""
    path = project / SUMMARIES_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    text = summaries if isinstance(summaries, str) else json.dumps(summaries)
    path.write_text(text, encoding="utf-8")
    return path
