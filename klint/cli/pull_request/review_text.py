"""The words of a pull request's review: its comments, its body and its replies."""

from klint.cli.pull_request.review_input import ReviewFinding, ReviewInput
from klint.cli.pull_request.review_plan import (
    ReviewPlan,
    format_finding_marker,
    format_gone_marker,
)

_NO_COMMAND_LINE = (
    "This finding has no `klint-ack` command; a wrong one is turned off in "
    "`klint.json`'s `rule_exclusions`."
)


def format_comment_body(finding: ReviewFinding) -> str:
    """Return an inline comment on ``finding``, ending in its hidden marker."""
    lines = [
        f"**klint** · `{finding.rule_id}` · confidence {_describe_confidence(finding)}",
        "",
        f"> {finding.question}",
        "",
        *_describe_acknowledgement(finding),
        "",
        format_finding_marker(finding.marker_id),
    ]
    return "\n".join(lines)


def format_review_body(review_input: ReviewInput, plan: ReviewPlan) -> str:
    """Return the review's body: the counts, then the findings not commented inline."""
    new_count = (
        len(plan.inline_comments)
        + len(plan.off_diff_findings)
        + len(plan.over_limit_findings)
    )
    total = new_count + len(plan.open_findings)
    lines = [
        f"### klint: {_count(total, 'finding')} at a minimum confidence of "
        f"{review_input.min_confidence}",
        "",
        f"- {new_count} new, {len(plan.open_findings)} still open from an "
        "earlier push.",
        f"- {_count(review_input.rule_exclusion_count, 'rule exclusion')} and "
        f"{_count(review_input.acknowledgement_count, 'acknowledgement')} applied.",
    ]
    if plan.gone_comments:
        lines.append(
            f"- {_count(len(plan.gone_comments), 'earlier finding')} gone, "
            "replied to in its thread."
        )
    if plan.off_diff_findings:
        lines += [
            "",
            "**Not on a line this pull request adds:**",
            "",
            *(_format_listed_finding(f) for f in plan.off_diff_findings),
        ]
    if plan.over_limit_findings:
        lines += [
            "",
            f"**{len(plan.over_limit_findings)} more, past the limit of inline "
            "comments:**",
            "",
            *(_format_listed_finding(f) for f in plan.over_limit_findings),
        ]
    return "\n".join(lines) + "\n"


def format_gone_reply(marker_id: str, commit_id: str) -> str:
    """Return the reply to a comment whose finding ``commit_id`` no longer has."""
    return (
        f"klint no longer finds this at {commit_id[:7]}: it was fixed or "
        "acknowledged, or its code changed.\n\n" + format_gone_marker(marker_id)
    )


def _format_listed_finding(finding: ReviewFinding) -> str:
    where = "the project" if finding.path is None else f"`{finding.path}`"
    if finding.span is not None:
        where += f" lines {finding.span.start}-{finding.span.end}"
    command = finding.acknowledge_command
    acknowledge = "" if command is None else f" · `{command}`"
    return (
        f"- {where} · `{finding.rule_id}` · {_describe_confidence(finding)} · "
        f"{finding.question}{acknowledge} {format_finding_marker(finding.marker_id)}"
    )


def _describe_acknowledgement(finding: ReviewFinding) -> list[str]:
    if finding.acknowledge_command is None:
        return [_NO_COMMAND_LINE]
    return [
        "If it is wrong, acknowledge it in your checkout and push the log:",
        "",
        "```",
        finding.acknowledge_command,
        "```",
    ]


def _describe_confidence(finding: ReviewFinding) -> str:
    return "—" if finding.confidence is None else f"{finding.confidence:.2f}"


def _count(count: int, noun: str) -> str:
    return f"1 {noun}" if count == 1 else f"{count} {noun}s"
