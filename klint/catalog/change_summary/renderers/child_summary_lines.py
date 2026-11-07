"""How a summary one level down is shown as evidence for the level above it."""

from collections.abc import Sequence
from dataclasses import dataclass
from enum import Enum

from klint.catalog.change_summary.summary_accuracy_scale import CANNOT_TELL
from klint.catalog.change_summary.summary_check_tag import SummaryCheckTag
from klint.core.models.report import AuditFinding


class ChildSummaryVerdict(Enum):
    """What the checks of a summary one level down found.

    PASSED: every check passed. UNCLEAR: no check failed, but the judge
    could not tell for an accuracy check. INCOMPLETE: only completeness
    checks failed, so what it says still holds. FAILED: another check
    failed. NOT_CHECKED: it has no findings, as when its audit failed.
    """

    PASSED = "passed"
    UNCLEAR = "unclear"
    INCOMPLETE = "incomplete"
    FAILED = "failed"
    NOT_CHECKED = "not_checked"


# The note shown after a child's name; a summary that passed has none.
_VERDICT_TO_NOTE = {
    ChildSummaryVerdict.PASSED: "",
    ChildSummaryVerdict.UNCLEAR: " (its summary could not be fully checked)",
    ChildSummaryVerdict.INCOMPLETE: " (its summary may leave out changes)",
    ChildSummaryVerdict.FAILED: " (its summary failed its own check)",
    ChildSummaryVerdict.NOT_CHECKED: " (its summary was not checked)",
}


@dataclass(frozen=True)
class ChildSummary:
    """A summary one level down: what to call it, its ID and its text."""

    name: str
    unit_id: str
    summary: str


def find_child_verdict(findings: Sequence[AuditFinding]) -> ChildSummaryVerdict:
    """Return what ``findings``, those on one child summary, say about it."""
    if not findings:
        return ChildSummaryVerdict.NOT_CHECKED
    problems = [finding for finding in findings if finding.is_problem()]
    if problems:
        is_only_incomplete = all(
            SummaryCheckTag.COMPLETENESS in problem.tags
            and SummaryCheckTag.ACCURACY not in problem.tags
            for problem in problems
        )
        return (
            ChildSummaryVerdict.INCOMPLETE
            if is_only_incomplete
            else ChildSummaryVerdict.FAILED
        )
    if any(
        SummaryCheckTag.ACCURACY in finding.tags
        and finding.answer.key == CANNOT_TELL.key
        for finding in findings
    ):
        return ChildSummaryVerdict.UNCLEAR
    return ChildSummaryVerdict.PASSED


def list_child_summary_lines(
    children: Sequence[ChildSummary], child_findings: Sequence[AuditFinding]
) -> list[str]:
    """Return a line per child: its name, what its checks found, and its summary."""
    lines: list[str] = []
    for child in children:
        verdict = find_child_verdict(
            [finding for finding in child_findings if finding.unit_id == child.unit_id]
        )
        lines.append(f"- {child.name}{_VERDICT_TO_NOTE[verdict]}: {child.summary}")
    return lines
