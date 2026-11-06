"""The measures of a judge on the set: mistakes caught, true summaries flagged.

A summary the judge refused is a refusal, never a miss or a false alarm:
it is left out of every share but the count of refusals.
"""

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from enum import StrEnum

from judge_accuracy.change_summary.case_set import MistakeKind
from judge_accuracy.change_summary.judged_summary import (
    MISTAKE_KIND_TO_OWN_CHECKS,
    JudgedSummary,
)
from klint.catalog.change_summary.units.summary_context import SummaryLevel

# The confidence thresholds each run is also scored at, to choose one.
SWEPT_MIN_CONFIDENCES = (0.0, 0.3, 0.5, 0.6, 0.7, 0.75, 0.8, 0.9)


class SummaryGroup(StrEnum):
    """A level of summary; hunks split by whether their code fit the budget."""

    HUNK_WITHIN_CUT = "hunk, code within the cut"
    HUNK_OVER_CUT = "hunk, code over the cut"
    FILE = "file"
    PACKAGE = "package"
    COMMIT = "commit"


# The group of a summary above the hunk level.
_LEVEL_TO_GROUP = {
    SummaryLevel.FILE: SummaryGroup.FILE,
    SummaryLevel.PACKAGE: SummaryGroup.PACKAGE,
    SummaryLevel.COMMIT: SummaryGroup.COMMIT,
}


@dataclass(frozen=True)
class Share:
    """part of whole, as "3/12 (25%)"; a share of nothing is shown as "-"."""

    part: int
    whole: int

    def format_share(self) -> str:
        if self.whole == 0:
            return "-"
        return f"{self.part}/{self.whole} ({round(100 * self.part / self.whole)}%)"


@dataclass(frozen=True)
class PlantedKindScore:
    """How the judge did on the planted mistakes of one kind.

    caught counts the mistakes with a failed check; caught_by_own_check
    those whose check written for the kind failed. cannot_tell is the share
    of all answers about them that were "cannot tell". mistake_kind is None
    for every kind together.
    """

    mistake_kind: MistakeKind | None
    planted_count: int
    refused_count: int
    caught: Share
    caught_by_own_check: Share
    cannot_tell: Share


@dataclass(frozen=True)
class TrueCheckScore:
    """How the checks of one kind of mistake did on the true summaries.

    mistake_kind is None for every check together. asked_count counts the
    true summaries those checks were asked about, and wrongly_flagged those
    a check failed on. cannot_tell is the share of their answers that were
    "cannot tell".
    """

    mistake_kind: MistakeKind | None
    asked_count: int
    wrongly_flagged: Share
    cannot_tell: Share


@dataclass(frozen=True)
class GroupScore:
    """Mistakes caught and true summaries flagged at one group of summaries."""

    group: SummaryGroup
    caught: Share
    wrongly_flagged: Share


@dataclass(frozen=True)
class ThresholdScore:
    """Mistakes caught and true summaries flagged at one confidence threshold."""

    min_confidence: float
    caught: Share
    wrongly_flagged: Share


@dataclass(frozen=True)
class ScoreCard:
    """Every measure of one run, at min_confidence unless a measure says not."""

    min_confidence: float
    planted_kind_scores: tuple[PlantedKindScore, ...]
    true_check_scores: tuple[TrueCheckScore, ...]
    group_scores: tuple[GroupScore, ...]
    threshold_scores: tuple[ThresholdScore, ...]
    missed_mistakes: tuple[JudgedSummary, ...]
    wrongly_flagged_summaries: tuple[JudgedSummary, ...]
    refused_summaries: tuple[JudgedSummary, ...]


def score_judged_summaries(
    judged: Sequence[JudgedSummary], min_confidence: float
) -> ScoreCard:
    """Return the measures of the judge on ``judged`` at ``min_confidence``."""
    planted = [summary for summary in judged if not summary.is_true()]
    true = [summary for summary in judged if summary.is_true()]
    answered_planted = [summary for summary in planted if not summary.is_refused()]
    answered_true = [summary for summary in true if not summary.is_refused()]
    return ScoreCard(
        min_confidence=min_confidence,
        planted_kind_scores=tuple(
            _score_planted_kind(kind, planted, min_confidence)
            for kind in (*MistakeKind, None)
        ),
        true_check_scores=tuple(
            _score_true_checks(kind, true, min_confidence)
            for kind in (*MistakeKind, None)
        ),
        group_scores=tuple(
            GroupScore(
                group=group,
                caught=_count_flagged(
                    _select_group(answered_planted, group), min_confidence
                ),
                wrongly_flagged=_count_flagged(
                    _select_group(answered_true, group), min_confidence
                ),
            )
            for group in SummaryGroup
        ),
        threshold_scores=tuple(
            ThresholdScore(
                min_confidence=threshold,
                caught=_count_flagged(answered_planted, threshold),
                wrongly_flagged=_count_flagged(answered_true, threshold),
            )
            for threshold in SWEPT_MIN_CONFIDENCES
        ),
        missed_mistakes=tuple(
            summary
            for summary in answered_planted
            if not summary.is_flagged(min_confidence)
        ),
        wrongly_flagged_summaries=tuple(
            summary for summary in answered_true if summary.is_flagged(min_confidence)
        ),
        refused_summaries=tuple(summary for summary in judged if summary.is_refused()),
    )


def find_summary_group(summary: JudgedSummary) -> SummaryGroup:
    """Return the group ``summary`` is scored in."""
    if summary.level is SummaryLevel.HUNK:
        return (
            SummaryGroup.HUNK_OVER_CUT
            if summary.is_over_cut
            else SummaryGroup.HUNK_WITHIN_CUT
        )
    return _LEVEL_TO_GROUP[summary.level]


def _score_planted_kind(
    kind: MistakeKind | None, planted: Sequence[JudgedSummary], min_confidence: float
) -> PlantedKindScore:
    of_kind = [
        summary for summary in planted if kind is None or summary.mistake_kind is kind
    ]
    answered = [summary for summary in of_kind if not summary.is_refused()]
    return PlantedKindScore(
        mistake_kind=kind,
        planted_count=len(of_kind),
        refused_count=len(of_kind) - len(answered),
        caught=_count_flagged(answered, min_confidence),
        caught_by_own_check=Share(
            sum(summary.is_caught_by_own_check(min_confidence) for summary in answered),
            len(answered),
        ),
        cannot_tell=_sum_share(
            answered,
            lambda summary: summary.count_cannot_tell_answers(),
            lambda summary: summary.count_answers(),
        ),
    )


def _score_true_checks(
    kind: MistakeKind | None, true: Sequence[JudgedSummary], min_confidence: float
) -> TrueCheckScore:
    checks = None if kind is None else MISTAKE_KIND_TO_OWN_CHECKS[kind]
    answered = [summary for summary in true if not summary.is_refused()]
    asked = (
        answered
        if checks is None
        else [summary for summary in answered if summary.is_asked(checks)]
    )
    return TrueCheckScore(
        mistake_kind=kind,
        asked_count=len(asked),
        wrongly_flagged=Share(
            sum(summary.is_flagged(min_confidence, checks) for summary in asked),
            len(asked),
        ),
        cannot_tell=_sum_share(
            asked,
            lambda summary: summary.count_cannot_tell_answers(checks),
            lambda summary: summary.count_answers(checks),
        ),
    )


def _select_group(
    judged: Sequence[JudgedSummary], group: SummaryGroup
) -> list[JudgedSummary]:
    return [summary for summary in judged if find_summary_group(summary) is group]


def _count_flagged(judged: Sequence[JudgedSummary], min_confidence: float) -> Share:
    """Return the share of ``judged`` a check failed on, with ``min_confidence``."""
    return Share(
        sum(summary.is_flagged(min_confidence) for summary in judged), len(judged)
    )


def _sum_share(
    judged: Sequence[JudgedSummary],
    count_part: Callable[[JudgedSummary], int],
    count_whole: Callable[[JudgedSummary], int],
) -> Share:
    return Share(
        sum(count_part(summary) for summary in judged),
        sum(count_whole(summary) for summary in judged),
    )
