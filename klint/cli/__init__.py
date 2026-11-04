"""klint's commands: one entry point per console script, and what they share."""

from klint.cli.change_summary_audit import (
    CHANGE_SUMMARY_COMMAND,
    run_change_summary_audit,
)
from klint.cli.exit_code import ExitCode
from klint.cli.file_audit import FILE_AUDIT_COMMAND, run_file_audit
from klint.cli.klint_project_alias import run_klint_project_alias
from klint.cli.runner import (
    AuditCommand,
    AuditCommandApp,
    parse_command_arguments,
)
from klint.cli.shell_invocation import run_command_from_shell
from klint.cli.structure_audit import STRUCTURE_AUDIT_COMMAND, run_structure_audit
from klint.cli.wiring import create_command_injector

__all__ = [
    "CHANGE_SUMMARY_COMMAND",
    "FILE_AUDIT_COMMAND",
    "STRUCTURE_AUDIT_COMMAND",
    "AuditCommand",
    "AuditCommandApp",
    "ExitCode",
    "create_command_injector",
    "parse_command_arguments",
    "run_change_summary_audit",
    "run_command_from_shell",
    "run_file_audit",
    "run_klint_project_alias",
    "run_structure_audit",
]
