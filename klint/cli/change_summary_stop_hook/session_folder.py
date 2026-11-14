"""Where the hook keeps what it records about one session.

Each session has a folder in the repository's git directory, so that what
the hook records is never part of the working tree, nor of the change the
summaries are about.
"""

import re
import subprocess
from pathlib import Path

# The hook's folder, relative to the git directory of the worktree.
_GIT_PATH = "klint/change-summary-stop-hook"
# A session ID names a folder, so it may hold only these characters.
_SESSION_ID_PATTERN = re.compile(r"[A-Za-z0-9_-]{1,128}")


def find_session_folder(project_path: Path, session_id: str) -> Path:
    """Return the folder of ``session_id`` in the git worktree of ``project_path``.

    The folder may not exist yet. Raises ValueError when the session ID
    cannot name a folder, or git cannot tell the worktree's git directory.
    """
    if not _SESSION_ID_PATTERN.fullmatch(session_id):
        raise ValueError(
            f"The session ID {session_id!r} is not one: it may hold only "
            "letters, digits, '-' and '_'"
        )
    try:
        output = run_git_in(
            project_path, "rev-parse", "--path-format=absolute", "--git-path", _GIT_PATH
        )
    except ValueError as error:
        raise ValueError(
            f"'{project_path}' is not in a git repository: {error}"
        ) from error
    return Path(output.strip()) / session_id


def run_git_in(directory: Path, *arguments: str) -> str:
    """Return what git prints for ``arguments`` in ``directory``.

    Raises ValueError when git cannot be run or the command fails.
    """
    try:
        completed = subprocess.run(
            ["git", *arguments],
            cwd=directory,
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError as error:
        raise ValueError(f"git cannot be run: {error}") from error
    if completed.returncode != 0:
        raise ValueError(
            f"git {' '.join(arguments)} failed in '{directory}': "
            f"{completed.stderr.strip()}"
        )
    return completed.stdout
