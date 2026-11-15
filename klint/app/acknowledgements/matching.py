"""Which findings an acknowledgement log has already judged wrong."""

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from klint.app.acknowledgements.finding_identity import identify_finding
from klint.core.models.acknowledgements import AcknowledgementEntry
from klint.core.models.reports import AuditFinding, JsonValue


@dataclass(frozen=True)
class AcknowledgedFinding:
    """A finding, and the acknowledged entry that says it is wrong."""

    finding: AuditFinding
    entry: AcknowledgementEntry

    def convert_to_dict(self) -> dict[str, JsonValue]:
        """Return the pair as JSON output gives it."""
        return {
            "entry_id": self.entry.entry_id,
            "rule_id": self.finding.rule_id,
            "unit_id": self.finding.unit_id,
            "acknowledged_at": self.entry.acknowledged_at,
            "note": self.entry.note,
        }


@dataclass(frozen=True)
class FindingSeparation:
    """Findings split into those still standing and those acknowledged."""

    open_findings: tuple[AuditFinding, ...]
    acknowledged_findings: tuple[AcknowledgedFinding, ...]


def separate_acknowledged_findings(
    findings: Sequence[AuditFinding],
    entries: Sequence[AcknowledgementEntry],
    repository_root: Path,
    working_directory: Path,
) -> FindingSeparation:
    """Split ``findings`` by whether an acknowledged entry in ``entries`` matches.

    A finding matches an entry when its rule, its unit's file and name, and
    the hash of the unit's code now on disk are the entry's. Open entries
    match nothing. The order of ``findings`` is kept on both sides.
    """
    entry_id_to_entry = {
        entry.entry_id: entry for entry in entries if not entry.is_open()
    }
    open_findings: list[AuditFinding] = []
    acknowledged: list[AcknowledgedFinding] = []
    for finding in findings:
        identity = identify_finding(finding, repository_root, working_directory)
        entry = (
            None
            if identity is None
            else entry_id_to_entry.get(identity.build_entry_id())
        )
        if entry is None:
            open_findings.append(finding)
        else:
            acknowledged.append(AcknowledgedFinding(finding=finding, entry=entry))
    return FindingSeparation(
        open_findings=tuple(open_findings), acknowledged_findings=tuple(acknowledged)
    )
