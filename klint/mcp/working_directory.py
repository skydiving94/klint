"""The paths a tool may audit: those inside the server's working directory."""

from pathlib import Path

from mcp.server.mcpserver.exceptions import ToolError


def resolve_path_inside(working_directory: Path, path: str) -> Path:
    """Return ``path`` relative to ``working_directory``, which it must be inside.

    A relative path is taken from the working directory. Raises ToolError
    for a path outside it, symbolic links followed, so that an agent can
    audit only the project the server was started in.
    """
    resolved = (working_directory / path).resolve()
    root = working_directory.resolve()
    if not resolved.is_relative_to(root):
        raise ToolError(
            f"'{path}' is outside the server's working directory '{root}'; "
            "klint-mcp audits paths inside it only"
        )
    return resolved.relative_to(root)
