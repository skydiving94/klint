"""The klint command: audits a file, or every file under a directory."""

import asyncio
import sys

from src.app.wiring import create_file_audit_path
from src.cli.runner import AuditCommand, run_command_from_shell

FILE_AUDIT_COMMAND = AuditCommand(
    name="klint",
    description="klint - Declarative Code Auditor CLI",
    target_argument_name="file",
    target_argument_help="Path to the code file or directory to audit",
    target_label="files",
    json_key="examined_files",
    create_audit_path=create_file_audit_path,
)


def cli_main() -> int:
    return asyncio.run(run_command_from_shell(FILE_AUDIT_COMMAND))


if __name__ == "__main__":
    sys.exit(cli_main())
