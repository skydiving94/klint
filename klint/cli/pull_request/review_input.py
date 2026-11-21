"""What a review is made of: its findings and the lines its diff adds."""

import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from klint.catalog.domain_neutral.git import parse_git_diff
from klint.core.models.reports import JsonValue

# As long as an acknowledgement log entry's ID, so that both look alike.
_MARKER_ID_LENGTH = 12


@dataclass(frozen=True)
class LineSpan:
    """The lines start to end of a file, both included."""

    start: int
    end: int

    def overlap(self, other: "LineSpan") -> "LineSpan | None":
        """Return the lines both spans hold; None when they hold none."""
        start, end = max(self.start, other.start), min(self.end, other.end)
        return LineSpan(start, end) if start <= end else None


@dataclass(frozen=True)
class ReviewFinding:
    """A finding of the pull request's audits, as its review shows it.

    marker_id names the finding across pushes: its acknowledgement log
    entry's ID, or, for a finding that cannot be logged, such as a
    directory's, a hash of its audit, rule and unit. span is None when the
    finding names no lines.
    """

    marker_id: str
    rule_id: str
    unit_id: str
    confidence: float | None
    question: str
    path: str | None
    span: LineSpan | None
    acknowledge_command: str | None


@dataclass(frozen=True)
class ReviewInput:
    """The findings at min_confidence, and what the audits turned off.

    path_to_added_spans holds, for each file the diff changes, the runs of
    lines it adds, which are lines a review comment can be on.
    """

    min_confidence: float
    findings: tuple[ReviewFinding, ...]
    rule_exclusion_count: int
    acknowledgement_count: int
    path_to_added_spans: dict[str, tuple[LineSpan, ...]]


def read_review_input(findings_json: Path, diff_file: Path) -> ReviewInput:
    """Return the review's input from the Action's ``findings_json`` and its diff.

    Raises ValueError naming the file when one cannot be read.
    """
    report = _read_json_object(findings_json)
    try:
        files = parse_git_diff(diff_file.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise ValueError(f"cannot read the diff {diff_file}: {error}") from error
    path_to_added_spans = {
        change.path: tuple(
            LineSpan(
                hunk.header.new_start,
                hunk.header.new_start + len(hunk.added_lines) - 1,
            )
            for hunk in change.hunks
            if hunk.added_lines
        )
        for change in files
    }
    return ReviewInput(
        min_confidence=float(str(report.get("min_confidence"))),
        findings=tuple(
            _read_finding(item) for item in _read_list(report.get("findings"))
        ),
        rule_exclusion_count=_count_in_reports(report, "applied_rule_exclusions"),
        acknowledgement_count=_count_in_reports(report, "applied_acknowledgements"),
        path_to_added_spans=path_to_added_spans,
    )


def _read_json_object(path: Path) -> Mapping[str, JsonValue]:
    try:
        value: JsonValue = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise ValueError(f"cannot read the findings {path}: {error}") from error
    if not isinstance(value, dict):
        raise ValueError(f"the findings {path} are not a JSON object")
    return value


def _read_list(value: JsonValue) -> list[Mapping[str, JsonValue]]:
    if not isinstance(value, Sequence) or isinstance(value, str):
        return []
    return [item for item in value if isinstance(item, Mapping)]


def _count_in_reports(report: Mapping[str, JsonValue], key: str) -> int:
    reports = report.get("reports")
    if not isinstance(reports, Mapping):
        return 0
    return sum(
        len(_read_list(audit_report.get(key)))
        for audit_report in reports.values()
        if isinstance(audit_report, Mapping)
    )


def _read_finding(finding: Mapping[str, JsonValue]) -> ReviewFinding:
    rule_id = str(finding.get("rule_id"))
    unit_id = str(finding.get("unit_id"))
    entry_id = finding.get("entry_id")
    location = finding.get("location")
    path, span = None, None
    if isinstance(location, Mapping):
        path = str(location.get("path"))
        span = _read_span(location.get("start_line"), location.get("end_line"))
    confidence = finding.get("confidence")
    command = finding.get("acknowledge_command")
    return ReviewFinding(
        marker_id=(
            entry_id
            if isinstance(entry_id, str)
            else _hash_marker_id(str(finding.get("audit")), rule_id, unit_id)
        ),
        rule_id=rule_id,
        unit_id=unit_id,
        confidence=float(confidence) if isinstance(confidence, int | float) else None,
        question=str(finding.get("question") or ""),
        path=path,
        span=span,
        acknowledge_command=command if isinstance(command, str) else None,
    )


def _read_span(start: JsonValue, end: JsonValue) -> LineSpan | None:
    if not isinstance(start, int):
        return None
    return LineSpan(start, end if isinstance(end, int) else start)


def _hash_marker_id(audit: str, rule_id: str, unit_id: str) -> str:
    text = "\n".join((audit, rule_id, unit_id))
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:_MARKER_ID_LENGTH]
