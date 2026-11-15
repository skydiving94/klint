"""How a command reports the findings the acknowledgement log covers."""

from collections.abc import Sequence

from klint.app.acknowledgements import ACKNOWLEDGEMENTS_FOLDER, AcknowledgedFinding

_BOLD = "\033[1m"
_DIM = "\033[2m"
_RESET = "\033[0m"


def format_acknowledged_findings(
    acknowledged_findings: Sequence[AcknowledgedFinding],
) -> str:
    """Write the findings left out because the project acknowledged them as wrong.

    Each line names the entry, the rule, the unit and the note.
    """
    folder = ACKNOWLEDGEMENTS_FOLDER.as_posix()
    lines = [f"{_BOLD}Findings acknowledged in the project's {folder}/:{_RESET}"]
    for acknowledged in acknowledged_findings:
        entry = acknowledged.entry
        lines.append(
            f"  {_DIM}-{_RESET} {_BOLD}{entry.rule_id}{_RESET} on "
            f"{acknowledged.finding.unit_id} ({entry.entry_id}): {entry.note}"
        )
    return "\n".join(lines) + "\n"
