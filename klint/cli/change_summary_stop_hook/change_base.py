"""Where the change the hook checks starts: the session's start commit, or HEAD."""

import json
from collections.abc import Mapping
from dataclasses import dataclass

from klint.cli.change_summary_stop_hook.session_start_commit import (
    SessionStartCommit,
)
from klint.core.models.reports import JsonValue

# The field of a summaries document that names the change it summarizes.
GIT_CHANGE_FIELD_NAME = "git_change"


@dataclass(frozen=True)
class ChangeBase:
    """The commit the change is measured from, up to the working tree.

    commit is its hash, or None for HEAD: the uncommitted change alone.
    warning tells the user why the base is HEAD although a start commit was
    recorded; it is None otherwise.
    """

    commit: str | None
    warning: str | None = None

    def format_git_change(self) -> str:
        """Return the "git_change" value the summaries must hold, as JSON."""
        if self.commit is None:
            return "{}"
        return json.dumps({"base": self.commit})

    def describe(self) -> str:
        """Return what the change is, for the agent."""
        if self.commit is None:
            return "the uncommitted change against HEAD"
        return (
            f"everything changed since commit {self.commit[:12]}, where this session "
            "started: the commits made since, and the uncommitted change"
        )

    def is_named_by(self, raw_document: JsonValue) -> bool:
        """Return True when the summaries name exactly this change."""
        if not isinstance(raw_document, Mapping):
            return False
        git_change = raw_document.get(GIT_CHANGE_FIELD_NAME)
        if not isinstance(git_change, Mapping):
            return False
        if self.commit is None:
            return git_change.get("commit") is None and git_change.get("base") is None
        return (
            git_change.get("commit") is None and git_change.get("base") == self.commit
        )


def choose_change_base(start_commit: SessionStartCommit) -> ChangeBase:
    """Return the base of the session's change: its start commit when it still holds.

    With no start commit recorded, the base is HEAD. A recorded commit that
    is no longer in HEAD's history, as after a rebase, an amend or a branch
    switch, gives HEAD too, with a warning.
    """
    commit = start_commit.read()
    if commit is None:
        return ChangeBase(None)
    if start_commit.is_in_history(commit):
        return ChangeBase(commit)
    return ChangeBase(
        None,
        warning=(
            f"The commit recorded at this session's start, {commit[:12]}, is no "
            "longer in the current branch's history, as after a rebase, an amend "
            "or a branch switch. Only the uncommitted change is checked; a change "
            "committed since the start is not"
        ),
    )
