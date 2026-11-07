"""How many times in a row the hook has blocked one session's stop.

The counts are kept in the repository's git directory, one file per
session, so they are never part of the working tree, nor of the change the
summaries are about.
"""

import re
import subprocess
from pathlib import Path

# Where the counts are kept, relative to the git directory of the worktree.
_GIT_PATH = "klint/change-summary-stop-hook"
# A session ID names a file, so it may hold only these characters.
_SESSION_ID_PATTERN = re.compile(r"[A-Za-z0-9_-]{1,128}")


class SessionBlockCount:
    """The number of stops in a row the hook has blocked in one session."""

    def __init__(self, path: Path) -> None:
        self._path = path

    @classmethod
    def open_for(cls, project_path: Path, session_id: str) -> "SessionBlockCount":
        """Return the count of ``session_id`` in the git worktree of ``project_path``.

        Raises ValueError when the session ID cannot name a file, or git
        cannot tell the worktree's git directory.
        """
        if not _SESSION_ID_PATTERN.fullmatch(session_id):
            raise ValueError(
                f"The session ID {session_id!r} is not one: it may hold only "
                "letters, digits, '-' and '_'"
            )
        try:
            completed = subprocess.run(
                [
                    "git",
                    "rev-parse",
                    "--path-format=absolute",
                    "--git-path",
                    _GIT_PATH,
                ],
                cwd=project_path,
                capture_output=True,
                text=True,
                check=False,
            )
        except OSError as error:
            raise ValueError(f"git cannot be run: {error}") from error
        if completed.returncode != 0:
            raise ValueError(
                f"'{project_path}' is not in a git repository: "
                f"{completed.stderr.strip()}"
            )
        return cls(Path(completed.stdout.strip()) / session_id)

    def read(self) -> int:
        """Return the blocks in a row; 0 when none is recorded or it is unreadable."""
        try:
            return int(self._path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return 0

    def write(self, count: int) -> None:
        """Record ``count`` blocks in a row."""
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(str(count), encoding="utf-8")

    def clear(self) -> None:
        """Forget the blocks: the next block is the first in a row."""
        self._path.unlink(missing_ok=True)
