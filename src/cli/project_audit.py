"""The klint-project command: audits the structure of a project directory."""

import asyncio
import sys

from src.app.wiring import create_project_audit_path
from src.cli.runner import AuditCommand, run_command_from_shell

PROJECT_AUDIT_COMMAND = AuditCommand(
    name="klint-project",
    description="klint - recursive project structure audit CLI",
    target_argument_name="directory",
    target_argument_help="Path to the project directory to audit",
    target_label="directories",
    json_key="examined_directories",
    create_audit_path=create_project_audit_path,
)


def cli_main() -> int:
    return asyncio.run(run_command_from_shell(PROJECT_AUDIT_COMMAND))


if __name__ == "__main__":
    sys.exit(cli_main())
