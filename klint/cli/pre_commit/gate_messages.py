"""What klint-pre-commit tells the person committing."""

from collections.abc import Sequence

from klint.app.acknowledgements import ACKNOWLEDGEMENTS_FOLDER, LogReconciliation
from klint.core.models.acknowledgements import AcknowledgementEntry

ACKNOWLEDGE_COMMAND_NAME = "klint-ack"


def describe_threshold(min_confidence: float, model_name: str) -> str:
    """Say which findings count, such as "confidence 0.5 or more, judge kev-4b"."""
    return f"confidence {min_confidence:g} or more, judge {model_name}"


def format_blocked_message(
    reconciliation: LogReconciliation, threshold_description: str
) -> str:
    """Return the message of a blocked commit: each open finding, and what to do."""
    open_entries = reconciliation.open_entries
    noun = "finding" if len(open_entries) == 1 else "findings"
    lines = [
        f"Commit blocked: {len(open_entries)} {noun} in the staged change "
        f"need{'s' if len(open_entries) == 1 else ''} a fix or an acknowledgement "
        f"({threshold_description})",
        "",
    ]
    for entry in open_entries:
        lines.extend(_format_entry(entry))
    lines.extend(
        [
            *_describe_log_changes(reconciliation),
            "Fix the code, or acknowledge a finding that is wrong with its "
            f"{ACKNOWLEDGE_COMMAND_NAME} command, then commit again. "
            "git commit --no-verify skips this check.",
        ]
    )
    return "\n".join(lines)


def format_passed_message(
    reconciliation: LogReconciliation,
    checked_unit_count: int,
    threshold_description: str,
) -> str:
    """Return the message of a commit that may go ahead."""
    noun = "unit" if checked_unit_count == 1 else "units"
    lines = [
        f"Staged change passes: {checked_unit_count} {noun} checked, no open "
        f"finding ({threshold_description})",
        *_describe_log_changes(reconciliation),
    ]
    return "\n".join(lines)


def _format_entry(entry: AcknowledgementEntry) -> list[str]:
    confidence = (
        ""
        if entry.finding.confidence is None
        else f"  confidence {entry.finding.confidence * 100:.1f}%"
    )
    lines = [
        f"  {entry.entry_id}  {entry.rule_id}  {entry.unit.describe()}{confidence}"
    ]
    if entry.finding.question:
        lines.append(f"      {entry.finding.question}")
    lines.append(
        f'      {ACKNOWLEDGE_COMMAND_NAME} {entry.entry_id} --note "<why this '
        'finding is wrong>"'
    )
    lines.append("")
    return lines


def _describe_log_changes(reconciliation: LogReconciliation) -> list[str]:
    """Say what was done to the log, one line each; none when nothing was."""
    lines: list[str] = []
    folder = ACKNOWLEDGEMENTS_FOLDER.as_posix()
    if reconciliation.added_entries:
        lines.append(
            f"Logged {_count(reconciliation.added_entries, 'new finding')} in "
            f"{folder}/ and staged the log"
        )
    if reconciliation.removed_entries:
        lines.append(
            f"Removed {_count(reconciliation.removed_entries, 'entry', 'entries')} "
            f"whose finding is gone from {folder}/ and staged the log"
        )
    if reconciliation.acknowledged_findings:
        count = len(reconciliation.acknowledged_findings)
        verb = "matches" if count == 1 else "match"
        lines.append(
            f"{_count(reconciliation.acknowledged_findings, 'finding')} {verb} an "
            "acknowledged entry and is not reported"
            if count == 1
            else f"{count} findings match acknowledged entries and are not reported"
        )
    return lines


def _count(items: Sequence[object], noun: str, plural: str | None = None) -> str:
    plural = plural or f"{noun}s"
    return f"{len(items)} {noun if len(items) == 1 else plural}"
