"""The klint commands, as the entry points describe theirs."""

from dataclasses import dataclass


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
    report says no_problems_message when it has no finding to show. A
    command with does_offer_diff takes --diff, which audits the staged change
    of the working directory's repository in place of a target.
    """

    target_argument_name: str
    target_argument_help: str
    audit_kind_id: str
    no_problems_message: str = "No architectural or semantic issues found."
    does_offer_diff: bool = False
