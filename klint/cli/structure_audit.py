"""The klint-structure command: audits the structure of a project directory."""

import asyncio
import sys

from klint.catalog.code import PROJECT_STRUCTURE_KIND_ID
from klint.cli.runner import AuditCommand, run_command_from_shell

STRUCTURE_AUDIT_COMMAND = AuditCommand(
    name="klint-structure",
    description="klint - recursive project structure audit CLI",
    target_argument_name="directory",
    target_argument_help="Path to the project directory to audit",
    audit_kind_id=PROJECT_STRUCTURE_KIND_ID,
    audited_units_json_key="examined_directories",
)


def cli_main() -> int:
    return asyncio.run(run_command_from_shell(STRUCTURE_AUDIT_COMMAND))


if __name__ == "__main__":
    sys.exit(cli_main())
