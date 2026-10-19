"""The klint command: audits a file, or every file under a directory."""

import asyncio
import sys

from klint.app.audit_mode import AuditMode
from klint.cli.runner import AuditCommand, run_command_from_shell

FILE_AUDIT_COMMAND = AuditCommand(
    name="klint",
    description="klint - Declarative Code Auditor CLI",
    target_argument_name="file",
    target_argument_help="Path to the code file or directory to audit",
    audit_mode=AuditMode.FILE_CONTENTS,
    json_key="examined_files",
)


def cli_main() -> int:
    return asyncio.run(run_command_from_shell(FILE_AUDIT_COMMAND))


if __name__ == "__main__":
    sys.exit(cli_main())
