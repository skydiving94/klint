"""The commit a session started at: what it changes is measured from there."""

import re
from pathlib import Path

from klint.cli.change_summary_stop_hook.session_folder import (
    find_session_folder,
    run_git_in,
)

_FILE_NAME = "start-commit"
_COMMIT_HASH_PATTERN = re.compile(r"[0-9a-f]{40,64}")


class SessionStartCommit:
    """The commit HEAD named when one session started, if it was recorded."""

    def __init__(self, path: Path, project_path: Path) -> None:
        self._path = path
        self._project_path = project_path

    @classmethod
    def open_for(cls, project_path: Path, session_id: str) -> "SessionStartCommit":
        """Return the record of ``session_id`` in the git worktree of ``project_path``.

        Raises ValueError when the session ID cannot name a folder, or git
        cannot tell the worktree's git directory.
        """
        folder = find_session_folder(project_path, session_id)
        return cls(folder / _FILE_NAME, project_path)

    def is_recorded(self) -> bool:
        return self._path.exists()

    def record_head(self) -> str | None:
        """Record the commit HEAD names and return its hash; None when there is none.

        A repository with no commit yet gets no record.
        """
        commit_hash = _resolve_commit(self._project_path, "HEAD")
        if commit_hash is None:
            self._path.unlink(missing_ok=True)
            return None
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(commit_hash, encoding="utf-8")
        return commit_hash

    def read(self) -> str | None:
        """Return the recorded hash; None when none is recorded or it is unreadable."""
        try:
            text = self._path.read_text(encoding="utf-8").strip()
        except OSError:
            return None
        return text if _COMMIT_HASH_PATTERN.fullmatch(text) else None

    def is_in_history(self, commit_hash: str) -> bool:
        """Return True when ``commit_hash`` is HEAD or one of its ancestors."""
        try:
            run_git_in(
                self._project_path, "merge-base", "--is-ancestor", commit_hash, "HEAD"
            )
        except ValueError:
            return False
        return True


def _resolve_commit(project_path: Path, revision: str) -> str | None:
    """Return the hash ``revision`` names in ``project_path``; None when none."""
    try:
        output = run_git_in(
            project_path,
            "rev-parse",
            "--verify",
            "--quiet",
            "--end-of-options",
            f"{revision}^{{commit}}",
        )
    except ValueError:
        return None
    return output.strip()
