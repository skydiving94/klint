"""The events Claude Code sends the hook on stdin: SessionStart and Stop."""

import json
from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

# The environment variable Claude Code sets to the project's root directory.
PROJECT_DIRECTORY_VARIABLE = "CLAUDE_PROJECT_DIR"
# The SessionStart sources that go on with a session begun earlier.
_CONTINUING_SOURCES = frozenset({"resume", "compact"})


class HookEventKind(StrEnum):
    """Which event of Claude Code's the hook answers."""

    SESSION_START = "SessionStart"
    STOP = "Stop"


@dataclass(frozen=True)
class HookEvent:
    """A session starts, or its agent is about to stop.

    session_id names the agent's session, and project_path is the directory
    of the project it works in. For a Stop, is_stop_hook_active tells that
    the agent is going on because a Stop hook blocked its last stop. For a
    SessionStart, is_continuing tells that the session began earlier and is
    resumed or compacted, not started afresh.
    """

    kind: HookEventKind
    session_id: str
    project_path: Path
    is_stop_hook_active: bool = False
    is_continuing: bool = False


def read_hook_event(event_text: str, environment: Mapping[str, str]) -> HookEvent:
    """Return the event ``event_text`` holds, as JSON.

    An event that names no hook_event_name is read as a Stop. The project is
    the directory CLAUDE_PROJECT_DIR names in ``environment``, else the
    event's "cwd". Raises ValueError when the text is not such an event.
    """
    try:
        raw_event = json.loads(event_text)
    except json.JSONDecodeError as error:
        raise ValueError(f"The hook event is not valid JSON: {error}") from error
    if not isinstance(raw_event, dict):
        raise ValueError("The hook event must be a JSON object")
    kind = _read_kind(raw_event.get("hook_event_name"))
    session_id = raw_event.get("session_id")
    if not isinstance(session_id, str):
        raise ValueError(
            f"The {kind} event's session_id {session_id!r} is not a session ID"
        )
    project_directory = environment.get(PROJECT_DIRECTORY_VARIABLE) or raw_event.get(
        "cwd"
    )
    if not isinstance(project_directory, str) or not project_directory:
        raise ValueError(
            f"Neither {PROJECT_DIRECTORY_VARIABLE} nor the {kind} event's cwd "
            "names the project directory"
        )
    return HookEvent(
        kind=kind,
        session_id=session_id,
        project_path=Path(project_directory),
        is_stop_hook_active=raw_event.get("stop_hook_active") is True,
        is_continuing=raw_event.get("source") in _CONTINUING_SOURCES,
    )


def _read_kind(raw_name: object) -> HookEventKind:
    if raw_name is None:
        return HookEventKind.STOP
    for kind in HookEventKind:
        if kind.value == raw_name:
            return kind
    raise ValueError(
        f"The hook answers {[kind.value for kind in HookEventKind]} events, "
        f"not {raw_name!r}"
    )
