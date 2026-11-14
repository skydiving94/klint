"""One klint command, as the entry points describe theirs."""

from dataclasses import dataclass


@dataclass(frozen=True)
class AuditCommand:
    """One klint command: its wording, its path argument and the audit it runs.

    name is what the user types and description is shown in the help.
    target_argument_name and target_argument_help describe the path to audit.
    audit_kind_id names the kind of audit the command asks for, and
    audited_units_json_key is the key the audited units are listed under in
    JSON output. The terminal report says no_problems_message when it has no
    finding to show. A command with does_offer_diff takes --diff, which
    audits the staged change of the working directory's repository in place
    of a target.
    """

    name: str
    description: str
    target_argument_name: str
    target_argument_help: str
    audit_kind_id: str
    audited_units_json_key: str
    no_problems_message: str = "No architectural or semantic issues found."
    does_offer_diff: bool = False
