"""A Claude Code Stop hook: the agent works on until klint passes its summaries.

The agent writes summaries of its change, measured from the commit the
session started at when the hook recorded it, else of its uncommitted
change; the hook checks them with the change-summary audit each time the
agent is about to stop.
"""

from klint.cli.change_summary_stop_hook.change_summary_stop_hook import (
    MAX_BLOCKS_IN_A_ROW,
    ChangeSummaryStopHook,
    run_change_summary_stop_hook,
)
from klint.cli.change_summary_stop_hook.hook_console import STOP_HOOK_COMMAND_NAME
from klint.cli.change_summary_stop_hook.hook_messages import (
    SUMMARIES_PATH,
    load_summary_instructions,
)

__all__ = [
    "MAX_BLOCKS_IN_A_ROW",
    "STOP_HOOK_COMMAND_NAME",
    "SUMMARIES_PATH",
    "ChangeSummaryStopHook",
    "load_summary_instructions",
    "run_change_summary_stop_hook",
]
