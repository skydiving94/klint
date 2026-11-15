"""The klint-pre-commit command: gates a commit on an audit of the staged change."""

from klint.cli.pre_commit.pre_commit_gate import (
    PRE_COMMIT_COMMAND,
    PreCommitGate,
    run_pre_commit_gate,
)

__all__ = ["PRE_COMMIT_COMMAND", "PreCommitGate", "run_pre_commit_gate"]
