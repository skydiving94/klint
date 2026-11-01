"""The klint-change-summary command: verifies an agent's summaries of a change."""

import asyncio
import sys

from klint.catalog.change_summary import CHANGE_SUMMARY_KIND_ID
from klint.cli.runner import AuditCommand, run_command_from_shell

CHANGE_SUMMARY_COMMAND = AuditCommand(
    name="klint-change-summary",
    description=(
        "klint - verifies an agent's summaries of a change, each hunk against "
        "its code and each file, package and the commit against the checked "
        "summaries below it"
    ),
    target_argument_name="summaries",
    target_argument_help="Path to the change-summary JSON document to verify",
    audit_kind_id=CHANGE_SUMMARY_KIND_ID,
    audited_units_json_key="examined_summaries",
    no_problems_message="Every summary passed its checks.",
)


def cli_main() -> int:
    return asyncio.run(run_command_from_shell(CHANGE_SUMMARY_COMMAND))


if __name__ == "__main__":
    sys.exit(cli_main())
