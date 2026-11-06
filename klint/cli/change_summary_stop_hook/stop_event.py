"""The Stop event Claude Code sends a Stop hook on stdin."""

import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

# The environment variable Claude Code sets to the project's root directory.
PROJECT_DIRECTORY_VARIABLE = "CLAUDE_PROJECT_DIR"


@dataclass(frozen=True)
class StopEvent:
    """An agent is about to stop.

    session_id names the agent's session, and project_path is the directory
    of the project it works in. is_stop_hook_active tells that the agent is
    going on because a Stop hook blocked its last stop.
    """

    session_id: str
    project_path: Path
    is_stop_hook_active: bool


def read_stop_event(event_text: str, environment: Mapping[str, str]) -> StopEvent:
    """Return the event ``event_text`` holds, as JSON.

    The project is the directory CLAUDE_PROJECT_DIR names in ``environment``,
    else the event's "cwd". Raises ValueError when the text is not such an
    event.
    """
    try:
        raw_event = json.loads(event_text)
    except json.JSONDecodeError as error:
        raise ValueError(f"The Stop event is not valid JSON: {error}") from error
    if not isinstance(raw_event, dict):
        raise ValueError("The Stop event must be a JSON object")
    session_id = raw_event.get("session_id")
    if not isinstance(session_id, str):
        raise ValueError(
            f"The Stop event's session_id {session_id!r} is not a session ID"
        )
    project_directory = environment.get(PROJECT_DIRECTORY_VARIABLE) or raw_event.get(
        "cwd"
    )
    if not isinstance(project_directory, str) or not project_directory:
        raise ValueError(
            f"Neither {PROJECT_DIRECTORY_VARIABLE} nor the Stop event's cwd names "
            "the project directory"
        )
    return StopEvent(
        session_id=session_id,
        project_path=Path(project_directory),
        is_stop_hook_active=raw_event.get("stop_hook_active") is True,
    )
