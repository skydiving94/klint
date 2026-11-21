"""The commit gate: klint-pre-commit, klint-ack, and how audits report the log."""

from klint.cli.pre_commit.acknowledge import acknowledge_entry, run_acknowledge
from klint.cli.pre_commit.acknowledged_findings import format_acknowledged_findings
from klint.cli.pre_commit.gate_arguments import PRE_COMMIT_COMMAND
from klint.cli.pre_commit.pre_commit_gate import PreCommitGate, run_pre_commit_gate

__all__ = [
    "PRE_COMMIT_COMMAND",
    "PreCommitGate",
    "acknowledge_entry",
    "format_acknowledged_findings",
    "run_acknowledge",
    "run_pre_commit_gate",
]
