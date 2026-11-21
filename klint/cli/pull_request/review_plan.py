"""Which findings a push's review comments on, lists in its body, or marks gone."""

import re
from collections.abc import Sequence
from dataclasses import dataclass

from klint.cli.pull_request.review_input import LineSpan, ReviewFinding, ReviewInput
from klint.infra.github import ExistingComment

# GitHub's reviews endpoint is kept to this many inline comments a review.
INLINE_COMMENT_LIMIT = 50
_FINDING_MARKER = re.compile(r"<!-- klint-finding:([0-9a-f]+) -->")
_GONE_MARKER = re.compile(r"<!-- klint-gone:([0-9a-f]+) -->")


def format_finding_marker(marker_id: str) -> str:
    """Return the hidden marker that names a finding in a comment or a review."""
    return f"<!-- klint-finding:{marker_id} -->"


def format_gone_marker(marker_id: str) -> str:
    """Return the hidden marker of the reply that says a finding is gone."""
    return f"<!-- klint-gone:{marker_id} -->"


@dataclass(frozen=True)
class InlineComment:
    """A new finding, to comment on the lines ``span`` of its file."""

    finding: ReviewFinding
    path: str
    span: LineSpan


@dataclass(frozen=True)
class GoneComment:
    """An earlier comment whose finding the latest push no longer has."""

    marker_id: str
    comment_id: int


@dataclass(frozen=True)
class ReviewPlan:
    """What one push posts.

    inline_comments are new findings on lines the diff adds. off_diff_findings
    are new findings a comment cannot be on, such as a directory's, and
    over_limit_findings the new ones past the inline limit; both go in the
    review's body. open_findings were posted by an earlier push.
    """

    inline_comments: tuple[InlineComment, ...]
    off_diff_findings: tuple[ReviewFinding, ...]
    over_limit_findings: tuple[ReviewFinding, ...]
    open_findings: tuple[ReviewFinding, ...]
    gone_comments: tuple[GoneComment, ...]

    def has_new_findings(self) -> bool:
        """Return True when this push has a finding no earlier one posted."""
        return bool(
            self.inline_comments or self.off_diff_findings or self.over_limit_findings
        )


def plan_review(
    review_input: ReviewInput,
    comments: Sequence[ExistingComment],
    review_bodies: Sequence[str],
    inline_limit: int = INLINE_COMMENT_LIMIT,
) -> ReviewPlan:
    """Return what to post, given the pull request's earlier comments and reviews.

    A finding whose marker is in an earlier comment or review is not posted
    again. A first comment of a thread whose finding is gone, and that has
    no reply saying so, is marked gone.
    """
    posted_ids = {
        marker_id
        for text in (*(comment.body for comment in comments), *review_bodies)
        for marker_id in _FINDING_MARKER.findall(text)
    }
    replied_ids = {
        marker_id
        for comment in comments
        for marker_id in _GONE_MARKER.findall(comment.body)
    }
    inline: list[InlineComment] = []
    off_diff: list[ReviewFinding] = []
    over_limit: list[ReviewFinding] = []
    open_findings: list[ReviewFinding] = []
    seen_ids: set[str] = set()
    for finding in review_input.findings:
        if finding.marker_id in seen_ids:
            continue
        seen_ids.add(finding.marker_id)
        if finding.marker_id in posted_ids:
            open_findings.append(finding)
            continue
        span = _locate_on_diff(finding, review_input.path_to_added_spans)
        if span is None or finding.path is None:
            off_diff.append(finding)
        elif len(inline) >= inline_limit:
            over_limit.append(finding)
        else:
            inline.append(InlineComment(finding, finding.path, span))
    gone = [
        GoneComment(marker_id, comment.comment_id)
        for comment in comments
        if comment.in_reply_to_id is None
        for marker_id in _FINDING_MARKER.findall(comment.body)
        if marker_id not in seen_ids and marker_id not in replied_ids
    ]
    return ReviewPlan(
        inline_comments=tuple(inline),
        off_diff_findings=tuple(off_diff),
        over_limit_findings=tuple(over_limit),
        open_findings=tuple(open_findings),
        gone_comments=tuple(gone),
    )


def _locate_on_diff(
    finding: ReviewFinding, path_to_added_spans: dict[str, tuple[LineSpan, ...]]
) -> LineSpan | None:
    """Return the first run of lines the diff adds inside the finding's lines.

    A finding that names no lines is put on its file's first added run.
    """
    added_spans = path_to_added_spans.get(finding.path or "", ())
    if finding.span is None:
        return added_spans[0] if added_spans else None
    for added_span in added_spans:
        overlap = finding.span.overlap(added_span)
        if overlap is not None:
            return overlap
    return None
