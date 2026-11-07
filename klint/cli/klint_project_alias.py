"""The klint-project command: the old name of klint-structure, kept for one release."""

import asyncio
import sys

from klint.cli.runner import print_warning_line, run_command_from_shell
from klint.cli.structure_audit import STRUCTURE_AUDIT_COMMAND
from klint.core.klint_warning import describe_deprecated_name

_OLD_COMMAND_NAME = "klint-project"


def cli_main() -> int:
    print_warning_line(
        STRUCTURE_AUDIT_COMMAND,
        describe_deprecated_name(_OLD_COMMAND_NAME, STRUCTURE_AUDIT_COMMAND.name),
    )
    return asyncio.run(run_command_from_shell(STRUCTURE_AUDIT_COMMAND))


if __name__ == "__main__":
    sys.exit(cli_main())
