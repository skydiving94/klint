"""One labelled summary of the set, and what the judge found about it."""

from collections.abc import Set
from dataclasses import dataclass
from enum import StrEnum

from judge_accuracy.change_summary.case_set import MistakeKind
from klint.catalog.change_summary.summary_accuracy_scale import CANNOT_TELL
from klint.catalog.change_summary.units.summary_context import SummaryLevel
from klint.core.models.reports import AuditFinding


class SummaryCheck(StrEnum):
    """The checks every change summary is asked, by their rule IDs."""

    NO_FALSE_STATEMENT = "no_false_statement"
    NO_UNSUPPORTED_REASON = "no_unsupported_reason"
    NO_CONTRADICTION_WITH_LEVEL_BELOW = "no_contradiction_with_level_below"
    COVERS_EVERY_CHANGE = "covers_every_change"
    COVERS_KEY_CHANGES = "covers_key_changes"


# The checks written to catch each kind of mistake.
MISTAKE_KIND_TO_OWN_CHECKS: dict[MistakeKind, frozenset[SummaryCheck]] = {
    MistakeKind.FALSE_STATEMENT: frozenset({SummaryCheck.NO_FALSE_STATEMENT}),
    MistakeKind.UNSUPPORTED_REASON: frozenset({SummaryCheck.NO_UNSUPPORTED_REASON}),
    MistakeKind.CONTRADICTION: frozenset(
        {SummaryCheck.NO_CONTRADICTION_WITH_LEVEL_BELOW}
    ),
    MistakeKind.OMISSION: frozenset(
        {SummaryCheck.COVERS_EVERY_CHANGE, SummaryCheck.COVERS_KEY_CHANGES}
    ),
}


@dataclass(frozen=True)
class JudgedSummary:
    """A labelled summary and the findings the judge gave about it.

    case_file_name names the case file it comes from and unit_id its unit.
    is_over_cut tells that its evidence did not fit within the character
    budget, so the judge read only part of it. mistake_kind is None for a
    true summary, and planted_number the number of a planted one in its case
    file, from 1. findings are the findings on its unit, None when the judge
    refused to answer about it; an answer to no check is a refusal too.
    """

    case_file_name: str
    unit_id: str
    level: SummaryLevel
    is_over_cut: bool
    mistake_kind: MistakeKind | None
    findings: tuple[AuditFinding, ...] | None
    planted_number: int | None = None

    def is_true(self) -> bool:
        return self.mistake_kind is None

    def is_refused(self) -> bool:
        return not self.findings

    def is_flagged(
        self, min_confidence: float, checks: Set[SummaryCheck] | None = None
    ) -> bool:
        """Return True when a check failed with at least ``min_confidence``.

        Only the findings of ``checks`` count, when given.
        """
        return any(
            finding.is_problem() and finding.does_meet_confidence(min_confidence)
            for finding in self._select_findings(checks)
        )

    def is_caught_by_own_check(self, min_confidence: float) -> bool:
        """Return True when a check written for its kind of mistake failed.

        A true summary has no kind of mistake, so it never is.
        """
        if self.mistake_kind is None:
            return False
        return self.is_flagged(
            min_confidence, MISTAKE_KIND_TO_OWN_CHECKS[self.mistake_kind]
        )

    def is_asked(self, checks: Set[SummaryCheck]) -> bool:
        """Return True when the judge answered one of ``checks`` about it."""
        return bool(self._select_findings(checks))

    def count_answers(self, checks: Set[SummaryCheck] | None = None) -> int:
        """Return how many checks the judge answered, of ``checks`` when given."""
        return len(self._select_findings(checks))

    def count_cannot_tell_answers(self, checks: Set[SummaryCheck] | None = None) -> int:
        """Return how many answers were "cannot tell", of ``checks`` when given."""
        return sum(
            finding.answer.key == CANNOT_TELL.key
            for finding in self._select_findings(checks)
        )

    def _select_findings(
        self, checks: Set[SummaryCheck] | None
    ) -> tuple[AuditFinding, ...]:
        findings = self.findings or ()
        if checks is None:
            return findings
        check_ids = {check.value for check in checks}
        return tuple(finding for finding in findings if finding.rule_id in check_ids)
