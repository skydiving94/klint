"""The instructions for writing change summaries, as shipped with klint."""

from enum import Enum
from importlib import resources
from string import Template

_INSTRUCTIONS_RESOURCE = "change_summary_stop_hook/writing_change_summaries.md"


class InstructionsAudience(Enum):
    """Who reads the instructions, which says where the agent finds the change.

    STOP_HOOK: an agent the Stop hook sends back, in a message that names
    the change and lists its files and hunks above the instructions.
    ANY_AGENT: any agent, given the instructions on their own, with the
    skeleton of the change beside them.
    """

    STOP_HOOK = "stop_hook"
    ANY_AGENT = "any_agent"


_STOP_HOOK_FIELDS = {
    "git_change_forms": (
        "exactly as this message says above: `{}` is the uncommitted change "
        'against HEAD; `{"base": "<commit>"}` is everything since that commit, '
        "the commits you made included, up to the working tree. Both take "
        "staged and unstaged edits, and untracked files that are not ignored."
    ),
    "hunk_header_source": "as the `git diff -U0` command above writes it",
}
_ANY_AGENT_FIELDS = {
    "git_change_forms": (
        "exactly as the skeleton from `klint-change-summary --skeleton` gives "
        "it: `{}` is the uncommitted change against HEAD, staged and unstaged "
        "edits and untracked files that are not ignored; "
        '`{"commit": "<commit>"}` is that commit alone, against its first parent.'
    ),
    "hunk_header_source": (
        "as the skeleton lists it, which is as `git diff -U0` writes it"
    ),
}
_audience_to_fields = {
    InstructionsAudience.STOP_HOOK: _STOP_HOOK_FIELDS,
    InstructionsAudience.ANY_AGENT: _ANY_AGENT_FIELDS,
}


def load_summary_instructions(audience: InstructionsAudience) -> str:
    """Return the instructions for writing the summaries, worded for ``audience``."""
    instructions = resources.files("klint.resources") / _INSTRUCTIONS_RESOURCE
    template = Template(instructions.read_text(encoding="utf-8").strip())
    return template.substitute(_audience_to_fields[audience])
