"""klint's commands: one entry point per console script, and what they share."""

from klint.cli.audit_command import AuditCommand
from klint.cli.change_summary_audit import (
    CHANGE_SUMMARY_COMMAND,
    run_change_summary_audit,
)
from klint.cli.change_summary_stop_hook import (
    ChangeSummaryStopHook,
    run_change_summary_stop_hook,
)
from klint.cli.command_arguments import parse_command_arguments
from klint.cli.exit_code import ExitCode
from klint.cli.file_audit import FILE_AUDIT_COMMAND, run_file_audit
from klint.cli.klint_project_alias import run_klint_project_alias
from klint.cli.pre_commit import (
    PRE_COMMIT_COMMAND,
    PreCommitGate,
    acknowledge_entry,
    run_acknowledge,
    run_pre_commit_gate,
)
from klint.cli.runner import AuditCommandApp
from klint.cli.shell_invocation import run_command_from_shell
from klint.cli.structure_audit import STRUCTURE_AUDIT_COMMAND, run_structure_audit

__all__ = [
    "CHANGE_SUMMARY_COMMAND",
    "FILE_AUDIT_COMMAND",
    "PRE_COMMIT_COMMAND",
    "STRUCTURE_AUDIT_COMMAND",
    "AuditCommand",
    "AuditCommandApp",
    "ChangeSummaryStopHook",
    "ExitCode",
    "PreCommitGate",
    "acknowledge_entry",
    "parse_command_arguments",
    "run_acknowledge",
    "run_change_summary_audit",
    "run_change_summary_stop_hook",
    "run_command_from_shell",
    "run_file_audit",
    "run_klint_project_alias",
    "run_pre_commit_gate",
    "run_structure_audit",
]
