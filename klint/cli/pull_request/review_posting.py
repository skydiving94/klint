"""Posting one push's review on a pull request, and marking its gone findings.

What happens goes to the job summary; nothing here changes the check's
pass or fail.
"""

from dataclasses import dataclass, replace
from http import HTTPStatus
from pathlib import Path
from typing import Protocol

from klint.cli.pull_request.review_input import ReviewInput, read_review_input
from klint.cli.pull_request.review_plan import ReviewPlan, plan_review
from klint.cli.pull_request.review_text import (
    format_comment_body,
    format_gone_reply,
    format_review_body,
)
from klint.infra.github import (
    DraftComment,
    ExistingComment,
    GitHubApiError,
    ReviewDraft,
)

_NO_WRITE_STATUSES = (HTTPStatus.FORBIDDEN, HTTPStatus.NOT_FOUND)
NO_WRITE_LINE = (
    "klint posted no review comments: the job's token cannot write to this "
    "pull request, as on a pull request from a fork. The workflow needs "
    "`pull-requests: write`."
)


class GitHubReviewClient(Protocol):
    """What posting a review needs of GitHub, for one pull request."""

    def list_review_comments(self) -> list[ExistingComment]: ...

    def list_review_bodies(self) -> list[str]: ...

    def create_review(self, draft: ReviewDraft) -> None: ...

    def reply_to_comment(self, comment_id: int, body: str) -> None: ...

    def find_unresolved_threads(self) -> dict[int, str]: ...

    def resolve_thread(self, thread_id: str) -> None: ...


@dataclass(frozen=True)
class ReviewArguments:
    """The Action's ``findings_json``, the diff it audited, and the head commit."""

    findings_json: Path
    diff_file: Path
    commit_id: str


def post_pull_request_review(
    arguments: ReviewArguments, client: GitHubReviewClient
) -> str:
    """Post this push's review through ``client``; return the job summary's lines.

    One review with the COMMENT event, only when the push has a finding no
    earlier push posted. Each earlier comment whose finding is gone gets
    one reply, and its thread is resolved where the token can.
    """
    try:
        review_input = read_review_input(arguments.findings_json, arguments.diff_file)
    except ValueError as error:
        return f"klint posted no review comments: {error}\n"
    try:
        plan = plan_review(
            review_input, client.list_review_comments(), client.list_review_bodies()
        )
    except GitHubApiError as error:
        return f"klint posted no review comments: GitHub's API failed: {error}\n"
    try:
        lines = [_post_review(review_input, plan, arguments.commit_id, client)]
        lines += _mark_gone(plan, arguments.commit_id, client)
    except GitHubApiError as error:
        if error.status in _NO_WRITE_STATUSES:
            return NO_WRITE_LINE + "\n"
        return f"klint's review comments stopped: GitHub's API failed: {error}\n"
    return "".join(line + "\n" for line in lines if line)


def _post_review(
    review_input: ReviewInput,
    plan: ReviewPlan,
    commit_id: str,
    client: GitHubReviewClient,
) -> str:
    if not plan.has_new_findings():
        return (
            f"klint posted no review: no new finding, "
            f"{len(plan.open_findings)} still open from an earlier push."
        )
    draft = ReviewDraft(
        commit_id=commit_id,
        body=format_review_body(review_input, plan),
        comments=tuple(
            DraftComment(
                path=comment.path,
                start_line=comment.span.start,
                line=comment.span.end,
                body=format_comment_body(comment.finding),
            )
            for comment in plan.inline_comments
        ),
    )
    try:
        client.create_review(draft)
    except GitHubApiError as error:
        if error.status != HTTPStatus.UNPROCESSABLE_ENTITY or not draft.comments:
            raise
        # GitHub refuses a line it does not show in the pull request's diff,
        # so every finding goes in the body instead.
        plan = replace(
            plan,
            inline_comments=(),
            off_diff_findings=(
                *(comment.finding for comment in plan.inline_comments),
                *plan.off_diff_findings,
            ),
        )
        client.create_review(
            replace(draft, body=format_review_body(review_input, plan), comments=())
        )
        return (
            "klint posted a review with every finding in its body: GitHub "
            f"refused the inline comments ({error})."
        )
    in_body = len(plan.off_diff_findings) + len(plan.over_limit_findings)
    return (
        f"klint posted a review with {len(draft.comments)} inline comments "
        f"and {in_body} findings in its body."
    )


def _mark_gone(
    plan: ReviewPlan, commit_id: str, client: GitHubReviewClient
) -> list[str]:
    if not plan.gone_comments:
        return []
    for gone in plan.gone_comments:
        client.reply_to_comment(
            gone.comment_id, format_gone_reply(gone.marker_id, commit_id)
        )
    lines = [f"klint replied to {len(plan.gone_comments)} gone findings."]
    try:
        comment_id_to_thread_id = client.find_unresolved_threads()
        thread_ids = [
            comment_id_to_thread_id[gone.comment_id]
            for gone in plan.gone_comments
            if gone.comment_id in comment_id_to_thread_id
        ]
        for thread_id in thread_ids:
            client.resolve_thread(thread_id)
    except GitHubApiError as error:
        lines.append(f"klint could not resolve their threads: {error}")
        return lines
    lines.append(f"klint resolved {len(thread_ids)} of their threads.")
    return lines
