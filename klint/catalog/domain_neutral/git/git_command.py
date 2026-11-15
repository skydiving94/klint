"""Runs git commands for the readers of a repository's changes."""

import asyncio
import os
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class GitOutput:
    """What one git command gave back: its exit status and what it printed."""

    return_code: int
    stdout: str
    stderr: str


async def run_git_or_raise(
    arguments: Sequence[str],
    directory: Path,
    *,
    stdin_text: str | None = None,
    index_path: Path | None = None,
) -> str:
    """Return what the git command printed. Raises ValueError when it fails."""
    output = await run_git(
        arguments, directory, stdin_text=stdin_text, index_path=index_path
    )
    if output.return_code != 0:
        raise ValueError(
            f"git {' '.join(arguments)} failed in '{directory}': "
            f"{output.stderr.strip()}"
        )
    return output.stdout


async def run_git(
    arguments: Sequence[str],
    directory: Path,
    *,
    stdin_text: str | None = None,
    index_path: Path | None = None,
) -> GitOutput:
    """Run git with ``arguments`` in ``directory``, on ``index_path`` when given."""
    environment = None
    if index_path is not None:
        environment = {**os.environ, "GIT_INDEX_FILE": str(index_path)}
    try:
        process = await asyncio.create_subprocess_exec(
            "git",
            *arguments,
            cwd=directory,
            env=environment,
            stdin=asyncio.subprocess.DEVNULL
            if stdin_text is None
            else asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
    except FileNotFoundError as error:
        raise ValueError("git cannot be run: it is not on the PATH") from error
    except NotADirectoryError as error:
        raise ValueError(f"'{directory}' is not a directory") from error
    stdout, stderr = await process.communicate(
        None if stdin_text is None else stdin_text.encode("utf-8")
    )
    return GitOutput(
        return_code=process.returncode or 0,
        stdout=stdout.decode("utf-8", errors="replace"),
        stderr=stderr.decode("utf-8", errors="replace"),
    )
