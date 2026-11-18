"""A pull request's reviews and review comments, through GitHub's REST and GraphQL."""

import json
import urllib.error
import urllib.request
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

_PAGE_SIZE = 100
_TIMEOUT_SECONDS = 30
_API_VERSION = "2022-11-28"
_THREADS_QUERY = """
query($owner: String!, $name: String!, $number: Int!, $after: String) {
  repository(owner: $owner, name: $name) {
    pullRequest(number: $number) {
      reviewThreads(first: 100, after: $after) {
        pageInfo { hasNextPage endCursor }
        nodes { id isResolved comments(first: 1) { nodes { databaseId } } }
      }
    }
  }
}
"""
_RESOLVE_MUTATION = """
mutation($threadId: ID!) {
  resolveReviewThread(input: {threadId: $threadId}) { thread { id } }
}
"""

JsonObject = Mapping[str, object]


class GitHubApiError(Exception):
    """A call GitHub refused, or one that failed to reach it (status None)."""

    def __init__(self, message: str, status: int | None) -> None:
        super().__init__(message)
        self.status = status


@dataclass(frozen=True)
class PullRequestAddress:
    """Where a pull request is: its repository as "owner/name", and its number.

    api_url and graphql_url are the GitHub server's, as a workflow's
    GITHUB_API_URL and GITHUB_GRAPHQL_URL give them.
    """

    repository: str
    number: int
    api_url: str = "https://api.github.com"
    graphql_url: str = "https://api.github.com/graphql"


@dataclass(frozen=True)
class ExistingComment:
    """A review comment already on the pull request.

    in_reply_to_id is the comment it replies to, or None for the first
    comment of its thread.
    """

    comment_id: int
    body: str
    in_reply_to_id: int | None


@dataclass(frozen=True)
class DraftComment:
    """A review comment to post on lines start_line to line of path's new side."""

    path: str
    start_line: int
    line: int
    body: str

    def convert_to_payload(self) -> dict[str, object]:
        """Return the comment as the reviews endpoint takes it."""
        payload: dict[str, object] = {
            "path": self.path,
            "line": self.line,
            "side": "RIGHT",
            "body": self.body,
        }
        if self.start_line != self.line:
            payload["start_line"] = self.start_line
            payload["start_side"] = "RIGHT"
        return payload


@dataclass(frozen=True)
class ReviewDraft:
    """A review to post on commit_id: a body, its inline comments, as a COMMENT."""

    commit_id: str
    body: str
    comments: tuple[DraftComment, ...]


class GitHubReviewApi:
    """Reads and writes one pull request's reviews with a token."""

    def __init__(self, address: PullRequestAddress, token: str) -> None:
        self._address = address
        self._token = token

    def list_review_comments(self) -> list[ExistingComment]:
        """Return every review comment on the pull request, replies included."""
        return [
            ExistingComment(
                comment_id=int(str(item["id"])),
                body=str(item.get("body") or ""),
                in_reply_to_id=_read_optional_int(item.get("in_reply_to_id")),
            )
            for item in self._list_pages("comments")
        ]

    def list_review_bodies(self) -> list[str]:
        """Return the body of every review on the pull request."""
        return [str(item.get("body") or "") for item in self._list_pages("reviews")]

    def create_review(self, draft: ReviewDraft) -> None:
        """Post ``draft`` as one review with the COMMENT event."""
        payload = {
            "commit_id": draft.commit_id,
            "body": draft.body,
            "event": "COMMENT",
            "comments": [comment.convert_to_payload() for comment in draft.comments],
        }
        self._send("POST", self._build_pull_url("reviews"), payload)

    def reply_to_comment(self, comment_id: int, body: str) -> None:
        """Post ``body`` as a reply in the thread of the comment ``comment_id``."""
        url = self._build_pull_url(f"comments/{comment_id}/replies")
        self._send("POST", url, {"body": body})

    def find_unresolved_threads(self) -> dict[int, str]:
        """Return each unresolved thread's ID by the ID of its first comment."""
        owner, name = self._address.repository.split("/", 1)
        comment_id_to_thread_id: dict[int, str] = {}
        cursor: str | None = None
        while True:
            variables = {
                "owner": owner,
                "name": name,
                "number": self._address.number,
                "after": cursor,
            }
            data = self._query(_THREADS_QUERY, variables)
            threads = _dig(data, "repository", "pullRequest", "reviewThreads")
            for thread in _read_list(threads.get("nodes")):
                first_comments = _read_list(_dig(thread, "comments").get("nodes"))
                if thread.get("isResolved") or not first_comments:
                    continue
                comment_id = int(str(first_comments[0]["databaseId"]))
                comment_id_to_thread_id[comment_id] = str(thread["id"])
            page_info = _dig(threads, "pageInfo")
            if not page_info.get("hasNextPage"):
                return comment_id_to_thread_id
            cursor = str(page_info["endCursor"])

    def resolve_thread(self, thread_id: str) -> None:
        """Mark the review thread ``thread_id`` resolved."""
        self._query(_RESOLVE_MUTATION, {"threadId": thread_id})

    def _build_pull_url(self, resource: str) -> str:
        address = self._address
        return (
            f"{address.api_url}/repos/{address.repository}/pulls/"
            f"{address.number}/{resource}"
        )

    def _list_pages(self, resource: str) -> list[JsonObject]:
        items: list[JsonObject] = []
        page = 1
        while True:
            url = f"{self._build_pull_url(resource)}?per_page={_PAGE_SIZE}&page={page}"
            batch = _read_list(self._send("GET", url, None))
            items.extend(batch)
            if len(batch) < _PAGE_SIZE:
                return items
            page += 1

    def _query(self, query: str, variables: Mapping[str, object]) -> JsonObject:
        reply = self._send(
            "POST", self._address.graphql_url, {"query": query, "variables": variables}
        )
        if not isinstance(reply, Mapping):
            raise GitHubApiError("GitHub's GraphQL API gave no object", None)
        errors = reply.get("errors")
        if errors:
            raise GitHubApiError(f"GitHub's GraphQL API refused: {errors}", None)
        return _dig(reply, "data")

    def _send(self, method: str, url: str, payload: object) -> object:
        data = None if payload is None else json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(url, data=data, method=method)
        request.add_header("Authorization", f"Bearer {self._token}")
        request.add_header("Accept", "application/vnd.github+json")
        request.add_header("X-GitHub-Api-Version", _API_VERSION)
        if data is not None:
            request.add_header("Content-Type", "application/json")
        try:
            with urllib.request.urlopen(request, timeout=_TIMEOUT_SECONDS) as response:
                text = response.read().decode("utf-8")
        except urllib.error.HTTPError as error:
            detail = error.read().decode("utf-8", errors="replace")[:300]
            raise GitHubApiError(
                f"{method} {url} gave {error.code}: {detail}", error.code
            ) from error
        except (urllib.error.URLError, OSError) as error:
            raise GitHubApiError(f"{method} {url} failed: {error}", None) from error
        return json.loads(text) if text else None


def _dig(value: object, *keys: str) -> JsonObject:
    for key in keys:
        if not isinstance(value, Mapping):
            raise GitHubApiError(f"GitHub's reply has no '{key}'", None)
        value = value.get(key)
    if not isinstance(value, Mapping):
        raise GitHubApiError(f"GitHub's reply has no object at '{keys[-1]}'", None)
    return value


def _read_list(value: object) -> list[JsonObject]:
    if not isinstance(value, Sequence) or isinstance(value, str):
        return []
    return [item for item in value if isinstance(item, Mapping)]


def _read_optional_int(value: object) -> int | None:
    return value if isinstance(value, int) else None
