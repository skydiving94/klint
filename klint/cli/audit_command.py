"""The klint commands, as the entry points describe theirs."""

from dataclasses import dataclass
from enum import StrEnum


class DiffOptions(StrEnum):
    """Which options a command offers to audit a change instead of a path."""

    # A path only.
    NONE = "none"
    # --diff, --diff-from and --diff-units: the units a change touches.
    CHANGED_UNITS = "changed_units"
    # --diff-from: the directories that hold a changed file, and their parents.
    CHANGED_DIRECTORIES = "changed_directories"


@dataclass(frozen=True)
class KlintCommand:
    """One klint command that takes no path to audit, such as a hook.

    name is what the user types, and what each line it prints on stderr
    starts with; description is shown in the help.
    """

    name: str
    description: str


@dataclass(frozen=True)
class AuditCommand(KlintCommand):
    """One klint command that audits a path: its path argument and its audit.

    target_argument_name and target_argument_help describe the path to audit.
    audit_kind_id names the kind of audit the command asks for. The terminal
    report says no_problems_message when it has no finding to show.
    diff_options says which options the command offers to audit a change in
    place of a target. does_offer_writing_aids adds --instructions and
    --skeleton, which print what helps an agent write change summaries in
    place of an audit.
    """

    target_argument_name: str
    target_argument_help: str
    audit_kind_id: str
    no_problems_message: str = "No architectural or semantic issues found."
    diff_options: DiffOptions = DiffOptions.NONE
    does_offer_writing_aids: bool = False
