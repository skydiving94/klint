"""How many times in a row the hook has blocked a session's stop.

The counts are kept in the repository's git directory, one file per
session, so they are never part of the working tree, nor of the change the
summaries are about.
"""

import subprocess
from pathlib import Path

# Where the counts are kept, relative to the git directory of the worktree.
_GIT_PATH = "klint/change-summary-stop-hook"


class BlockCountStore:
    """Keeps the number of blocks in a row of each session of one worktree."""

    def __init__(self, folder: Path) -> None:
        self._folder = folder

    @classmethod
    def open_for(cls, project_path: Path) -> "BlockCountStore":
        """Return the store of the git worktree ``project_path`` is in.

        Raises ValueError when git cannot tell its git directory.
        """
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
        return cls(Path(completed.stdout.strip()))

    def read_count(self, session_id: str) -> int:
        """Return the session's blocks in a row; 0 when none is recorded."""
        try:
            return int(self._locate(session_id).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return 0

    def write_count(self, session_id: str, count: int) -> None:
        """Record ``count`` blocks in a row for the session."""
        self._folder.mkdir(parents=True, exist_ok=True)
        self._locate(session_id).write_text(str(count), encoding="utf-8")

    def clear_count(self, session_id: str) -> None:
        """Forget the session's blocks: the next block is the first in a row."""
        self._locate(session_id).unlink(missing_ok=True)

    def _locate(self, session_id: str) -> Path:
        return self._folder / session_id
