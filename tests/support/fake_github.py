"""A stand-in for GitHub's API, holding one pull request's reviews in memory."""

from http import HTTPStatus

from klint.infra.github import (
    DraftComment,
    ExistingComment,
    GitHubApiError,
    ReviewDraft,
)


class FakeGitHub:
    """Records what a review posts, as GitHub would hold it.

    refused_status, when set, is the status every write fails with.
    refused_paths are files whose inline comments GitHub refuses with 422.
    can_resolve False makes resolving a thread fail.
    """

    def __init__(
        self,
        refused_status: HTTPStatus | None = None,
        refused_paths: tuple[str, ...] = (),
        can_resolve: bool = True,
    ) -> None:
        self.reviews: list[ReviewDraft] = []
        self.comments: list[ExistingComment] = []
        self.resolved_comment_ids: set[int] = set()
        self._refused_status = refused_status
        self._refused_paths = refused_paths
        self._can_resolve = can_resolve
        self._next_id = 1

    def list_review_comments(self) -> list[ExistingComment]:
        return list(self.comments)

    def list_review_bodies(self) -> list[str]:
        return [review.body for review in self.reviews]

    def create_review(self, draft: ReviewDraft) -> None:
        self._check_write()
        if any(comment.path in self._refused_paths for comment in draft.comments):
            raise GitHubApiError(
                "line not in the diff", HTTPStatus.UNPROCESSABLE_ENTITY
            )
        self.reviews.append(draft)
        for comment in draft.comments:
            self._add_comment(comment.body, None)

    def reply_to_comment(self, comment_id: int, body: str) -> None:
        self._check_write()
        self._add_comment(body, comment_id)

    def find_unresolved_threads(self) -> dict[int, str]:
        return {
            comment.comment_id: f"thread-{comment.comment_id}"
            for comment in self.comments
            if comment.in_reply_to_id is None
            and comment.comment_id not in self.resolved_comment_ids
        }

    def resolve_thread(self, thread_id: str) -> None:
        if not self._can_resolve:
            raise GitHubApiError("resource not accessible", None)
        self.resolved_comment_ids.add(int(thread_id.removeprefix("thread-")))

    def list_inline_comments(self) -> list[DraftComment]:
        """Return every inline comment of every review, in posting order."""
        return [comment for review in self.reviews for comment in review.comments]

    def list_replies(self) -> list[ExistingComment]:
        return [c for c in self.comments if c.in_reply_to_id is not None]

    def _check_write(self) -> None:
        if self._refused_status is not None:
            raise GitHubApiError("refused", self._refused_status)

    def _add_comment(self, body: str, in_reply_to_id: int | None) -> None:
        self.comments.append(ExistingComment(self._next_id, body, in_reply_to_id))
        self._next_id += 1
