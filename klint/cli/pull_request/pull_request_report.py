"""The findings of a pull request's two audits, combined for its check."""

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from klint.app.acknowledgements import identify_unit_finding
from klint.core.models.reports import JsonValue
from klint.core.models.units import Location

ACKNOWLEDGE_NOTE_PLACEHOLDER = "<why this finding is wrong>"


class PullRequestAudit(StrEnum):
    """One of the audits a pull request gets, named as the Action's modes are."""

    FILE = "file"
    STRUCTURE = "structure"


@dataclass(frozen=True)
class AuditReportFile:
    """The ``--json`` report one audit wrote, at ``path``."""

    audit: PullRequestAudit
    path: Path


@dataclass(frozen=True)
class PullRequestFinding:
    """One finding of a pull request's audits, with how to acknowledge it.

    entry_id is the ID its acknowledgement log entry has; None when the
    finding cannot be logged, as for a directory's.
    """

    audit: PullRequestAudit
    finding: Mapping[str, JsonValue]
    location: Location | None
    entry_id: str | None

    def describe_acknowledge_command(self) -> str | None:
        """Return the klint-ack command line for this finding; None without an entry."""
        if self.entry_id is None:
            return None
        return f'klint-ack {self.entry_id} --note "{ACKNOWLEDGE_NOTE_PLACEHOLDER}"'

    def convert_to_dict(self) -> dict[str, JsonValue]:
        """Return the finding as its report wrote it, with its audit and klint-ack."""
        return {
            **self.finding,
            "audit": self.audit.value,
            "entry_id": self.entry_id,
            "acknowledge_command": self.describe_acknowledge_command(),
        }


@dataclass(frozen=True)
class PullRequestReport:
    """What a pull request's audits found, at ``min_confidence``.

    audit_to_report holds each audit's whole ``--json`` report, and
    selected_unit_count how many units the two audits had to judge.
    """

    min_confidence: float
    findings: tuple[PullRequestFinding, ...]
    audit_to_report: dict[PullRequestAudit, Mapping[str, JsonValue]]
    selected_unit_count: int

    def convert_to_dict(self) -> dict[str, JsonValue]:
        """Return the report as the ``findings_json`` file holds it."""
        return {
            "min_confidence": self.min_confidence,
            "findings": [finding.convert_to_dict() for finding in self.findings],
            "reports": {
                audit.value: report for audit, report in self.audit_to_report.items()
            },
        }


def read_pull_request_report(
    report_files: tuple[AuditReportFile, ...],
    min_confidence: float,
    repository_root: Path | None,
    working_directory: Path,
) -> PullRequestReport:
    """Return the findings of the reports in ``report_files``, combined.

    Each finding's entry ID is that of the acknowledgement log of the
    repository at ``repository_root``; none outside a repository. Raises
    ValueError naming the file when a report cannot be read.
    """
    findings: list[PullRequestFinding] = []
    audit_to_report: dict[PullRequestAudit, Mapping[str, JsonValue]] = {}
    selected_unit_count = 0
    for report_file in report_files:
        report = _read_report(report_file.path)
        audit_to_report[report_file.audit] = report
        selected_unit_count += _count_selected_units(report)
        findings.extend(
            _read_finding(report_file.audit, item, repository_root, working_directory)
            for item in _list_findings(report)
        )
    return PullRequestReport(
        min_confidence=min_confidence,
        findings=tuple(findings),
        audit_to_report=audit_to_report,
        selected_unit_count=selected_unit_count,
    )


def _read_report(path: Path) -> Mapping[str, JsonValue]:
    """Return the JSON report at ``path``; raises ValueError when it is not one."""
    try:
        report: JsonValue = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise ValueError(f"cannot read the report {path}: {error}") from error
    if not isinstance(report, dict):
        raise ValueError(f"the report {path} is not a JSON object")
    return report


def _count_selected_units(report: Mapping[str, JsonValue]) -> int:
    """Return how many units the audit of a diff selected; every unit otherwise."""
    diff_change = report.get("diff_change")
    if isinstance(diff_change, Mapping):
        count = diff_change.get("selected_unit_count")
        return count if isinstance(count, int) else 0
    statuses = report.get("unit_id_to_roll_up_status")
    return len(statuses) if isinstance(statuses, Mapping) else 0


def _list_findings(report: Mapping[str, JsonValue]) -> list[Mapping[str, JsonValue]]:
    findings = report.get("findings")
    if not isinstance(findings, Sequence) or isinstance(findings, str):
        return []
    return [finding for finding in findings if isinstance(finding, Mapping)]


def _read_finding(
    audit: PullRequestAudit,
    finding: Mapping[str, JsonValue],
    repository_root: Path | None,
    working_directory: Path,
) -> PullRequestFinding:
    location = _read_location(finding.get("location"))
    entry_id = None
    if location is not None and repository_root is not None:
        identity = identify_unit_finding(
            str(finding["rule_id"]),
            str(finding["unit_id"]),
            location,
            repository_root,
            working_directory,
        )
        entry_id = None if identity is None else identity.build_entry_id()
    return PullRequestFinding(
        audit=audit, finding=finding, location=location, entry_id=entry_id
    )


def _read_location(value: JsonValue) -> Location | None:
    if not isinstance(value, Mapping) or "path" not in value:
        return None
    return Location(
        path=str(value["path"]),
        start_line=_read_line(value.get("start_line")),
        end_line=_read_line(value.get("end_line")),
    )


def _read_line(value: JsonValue) -> int | None:
    return value if isinstance(value, int) else None
