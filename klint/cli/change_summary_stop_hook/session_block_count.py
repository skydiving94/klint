"""How many times in a row the hook has blocked one session's stop."""

from pathlib import Path

from klint.cli.change_summary_stop_hook.session_folder import find_session_folder

_FILE_NAME = "block-count"


class SessionBlockCount:
    """The number of stops in a row the hook has blocked in one session."""

    def __init__(self, path: Path) -> None:
        self._path = path

    @classmethod
    def open_for(cls, project_path: Path, session_id: str) -> "SessionBlockCount":
        """Return the count of ``session_id`` in the git worktree of ``project_path``.

        Raises ValueError when the session ID cannot name a folder, or git
        cannot tell the worktree's git directory.
        """
        return cls(find_session_folder(project_path, session_id) / _FILE_NAME)

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
