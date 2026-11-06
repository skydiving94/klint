"""The score card of a run, written as Markdown to post on an issue."""

from collections.abc import Sequence
from dataclasses import dataclass

from judge_accuracy.change_summary.case_set import MistakeKind
from judge_accuracy.change_summary.judged_summary import (
    MISTAKE_KIND_TO_OWN_CHECKS,
    JudgedSummary,
)
from judge_accuracy.change_summary.scores import ScoreCard


@dataclass(frozen=True)
class RunDescription:
    """What a run asked and of whom, for the report's opening lines.

    judge_description names the judge. case_file_count, true_count and
    planted_count describe the set. asked_request_count and
    asked_character_count are the requests sent to the judge and the
    characters of subject they held; reused_request_count those answered
    from memory.
    """

    judge_description: str
    case_set_name: str
    case_file_count: int
    true_count: int
    planted_count: int
    asked_request_count: int
    asked_character_count: int
    reused_request_count: int


def format_score_report(card: ScoreCard, run: RunDescription) -> str:
    """Return the Markdown report of ``card`` for the run ``run`` describes."""
    lines = [
        f"## Change-summary accuracy: {run.judge_description}",
        "",
        f"- Set: `{run.case_set_name}`, {run.case_file_count} case files: "
        f"{run.true_count} true summaries, {run.planted_count} planted mistakes.",
        f"- Min confidence: {card.min_confidence}. Refused: "
        f"{len(card.refused_summaries)}.",
        f"- Judge requests: {run.asked_request_count} sent "
        f"({run.asked_character_count:,} characters of subject), "
        f"{run.reused_request_count} answered from memory.",
        "",
        "### Planted mistakes",
        "",
        "| Kind of mistake | Planted | Refused | Caught | Caught by its own check "
        '| "Cannot tell" answers |',
        "| --- | ---: | ---: | ---: | ---: | ---: |",
        *(
            f"| {_name_kind(score.mistake_kind)} | {score.planted_count} "
            f"| {score.refused_count} | {score.caught.format_share()} "
            f"| {score.caught_by_own_check.format_share()} "
            f"| {score.cannot_tell.format_share()} |"
            for score in card.planted_kind_scores
        ),
        "",
        "### True summaries",
        "",
        '| Checks for | Summaries asked | Wrongly flagged | "Cannot tell" answers |',
        "| --- | ---: | ---: | ---: |",
        *(
            f"| {_name_checks(score.mistake_kind)} | {score.asked_count} "
            f"| {score.wrongly_flagged.format_share()} "
            f"| {score.cannot_tell.format_share()} |"
            for score in card.true_check_scores
        ),
        "",
        "### By level",
        "",
        "| Level | Mistakes caught | True summaries wrongly flagged |",
        "| --- | ---: | ---: |",
        *(
            f"| {score.group.value} | {score.caught.format_share()} "
            f"| {score.wrongly_flagged.format_share()} |"
            for score in card.group_scores
        ),
        "",
        "### By confidence threshold",
        "",
        "| Min confidence | Mistakes caught | True summaries wrongly flagged |",
        "| ---: | ---: | ---: |",
        *(
            f"| {score.min_confidence} | {score.caught.format_share()} "
            f"| {score.wrongly_flagged.format_share()} |"
            for score in card.threshold_scores
        ),
        "",
        *_list_summaries("Mistakes missed", card.missed_mistakes, card),
        *_list_summaries(
            "True summaries wrongly flagged", card.wrongly_flagged_summaries, card
        ),
        *_list_summaries("Refused", card.refused_summaries, card),
    ]
    return "\n".join(lines).rstrip() + "\n"


def _name_kind(kind: MistakeKind | None) -> str:
    if kind is None:
        return "Every kind"
    return kind.value.replace("_", " ").capitalize()


def _name_checks(kind: MistakeKind | None) -> str:
    if kind is None:
        return "Every check"
    own_checks = MISTAKE_KIND_TO_OWN_CHECKS[kind]
    checks = ", ".join(sorted(check.value for check in own_checks))
    return f"{_name_kind(kind)} ({checks})"


def _list_summaries(
    title: str, summaries: Sequence[JudgedSummary], card: ScoreCard
) -> list[str]:
    """Return a section listing ``summaries``, or nothing when there are none."""
    if not summaries:
        return []
    return [
        f"### {title} ({len(summaries)})",
        "",
        *(f"- {_describe_summary(summary, card)}" for summary in summaries),
        "",
    ]


def _describe_summary(summary: JudgedSummary, card: ScoreCard) -> str:
    """Return the summary's case file, level, unit and what the judge failed it on."""
    label = "true" if summary.mistake_kind is None else _name_kind(summary.mistake_kind)
    failed_checks = ", ".join(
        f"{finding.rule_id} {finding.confidence:.2f}"
        if finding.confidence is not None
        else finding.rule_id
        for finding in summary.findings or ()
        if finding.is_problem() and finding.does_meet_confidence(card.min_confidence)
    )
    failures = f" - failed {failed_checks}" if failed_checks else ""
    return (
        f"`{summary.case_file_name}` {summary.level.value} `{summary.unit_id}` "
        f"({label.lower()}){failures}"
    )
