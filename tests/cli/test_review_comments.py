"""klint-pull-request review: one push's review comments, with a fake GitHub."""

import asyncio
import json
from http import HTTPStatus
from pathlib import Path
from typing import Any

import pytest

from klint.cli import ExitCode, run_pull_request_arguments
from klint.cli.pull_request import ReviewArguments, post_pull_request_review
from tests.support.fake_github import FakeGitHub

# A diff adding lines 10-12 of app.py and line 3 of util.py.
DIFF = """\
diff --git a/app.py b/app.py
index 1111111..2222222 100644
--- a/app.py
+++ b/app.py
@@ -9,0 +10,3 @@ def run():
+    password = "hunter2"
+    query = "SELECT " + name
+    return query
diff --git a/util.py b/util.py
index 3333333..4444444 100644
--- a/util.py
+++ b/util.py
@@ -3 +3 @@
-x = 1
+x = 2
"""


def build_finding(
    rule_id: str,
    entry_id: str | None,
    path: str | None = "app.py",
    lines: tuple[int, int] | None = (8, 14),
    audit: str = "file",
) -> dict[str, Any]:
    location = None
    if path is not None:
        start, end = lines if lines else (None, None)
        location = {"path": path, "start_line": start, "end_line": end}
    command = None if entry_id is None else f'klint-ack {entry_id} --note "<why>"'
    return {
        "rule_id": rule_id,
        "unit_id": f"{path}::run" if path else "klint",
        "confidence": 0.97,
        "question": f"Does it break {rule_id}?",
        "location": location,
        "audit": audit,
        "entry_id": entry_id,
        "acknowledge_command": command,
    }


def push(
    tmp_path: Path,
    github: FakeGitHub,
    findings: list[dict[str, Any]],
    commit_id: str = "a" * 40,
    reports: dict[str, Any] | None = None,
) -> str:
    """Post the review of one push whose findings are ``findings``."""
    findings_json = tmp_path / "findings.json"
    findings_json.write_text(
        json.dumps(
            {"min_confidence": 0.8, "findings": findings, "reports": reports or {}}
        ),
        encoding="utf-8",
    )
    diff_file = tmp_path / "pr.diff"
    diff_file.write_text(DIFF, encoding="utf-8")
    return post_pull_request_review(
        ReviewArguments(findings_json, diff_file, commit_id), github
    )


def test_each_finding_is_an_inline_comment_on_its_added_lines(tmp_path: Path) -> None:
    github = FakeGitHub()
    summary = push(tmp_path, github, [build_finding("hardcoded_secrets", "abc123")])

    assert len(github.reviews) == 1
    [comment] = github.list_inline_comments()
    assert (comment.path, comment.start_line, comment.line) == ("app.py", 10, 12)
    assert "`hardcoded_secrets`" in comment.body
    assert "0.97" in comment.body
    assert "Does it break hardcoded_secrets?" in comment.body
    assert 'klint-ack abc123 --note "<why>"' in comment.body
    assert "<!-- klint-finding:abc123 -->" in comment.body
    assert "1 inline comments" in summary


def test_a_finding_off_the_diff_and_a_structure_finding_go_in_the_body(
    tmp_path: Path,
) -> None:
    github = FakeGitHub()
    findings = [
        build_finding("long_function", "abc123", lines=(40, 60)),
        build_finding(
            "tidy_directory", None, path="klint", lines=None, audit="structure"
        ),
    ]
    push(tmp_path, github, findings)

    [review] = github.reviews
    assert review.comments == ()
    assert "`app.py` lines 40-60 · `long_function`" in review.body
    assert "`tidy_directory`" in review.body
    assert "<!-- klint-finding:abc123 -->" in review.body


def test_the_body_sums_up_new_open_exclusions_and_acknowledgements(
    tmp_path: Path,
) -> None:
    github = FakeGitHub()
    push(tmp_path, github, [build_finding("hardcoded_secrets", "abc123")])
    reports = {
        "file": {
            "applied_rule_exclusions": [{"rule_id": "x"}],
            "applied_acknowledgements": [{"id": "1"}, {"id": "2"}],
        }
    }
    findings = [
        build_finding("hardcoded_secrets", "abc123"),
        build_finding("missing_input_validation", "def456"),
    ]
    push(tmp_path, github, findings, reports=reports)

    body = github.reviews[1].body
    assert "2 findings at a minimum confidence of 0.8" in body
    assert "1 new, 1 still open from an earlier push" in body
    assert "1 rule exclusion and 2 acknowledgements applied" in body


def test_a_later_push_posts_no_duplicate(tmp_path: Path) -> None:
    github = FakeGitHub()
    finding = build_finding("hardcoded_secrets", "abc123")
    push(tmp_path, github, [finding])
    summary = push(tmp_path, github, [finding], commit_id="b" * 40)

    assert len(github.reviews) == 1
    assert "no new finding, 1 still open" in summary


def test_a_body_finding_is_not_posted_again(tmp_path: Path) -> None:
    github = FakeGitHub()
    finding = build_finding("tidy_directory", None, "klint", None, "structure")
    push(tmp_path, github, [finding])
    push(tmp_path, github, [finding])

    assert len(github.reviews) == 1


def test_a_gone_finding_gets_one_reply_and_its_thread_resolved(tmp_path: Path) -> None:
    github = FakeGitHub()
    secret = build_finding("hardcoded_secrets", "abc123")
    injection = build_finding("missing_input_validation", "def456")
    push(tmp_path, github, [secret, injection])
    summary = push(tmp_path, github, [injection], commit_id="b" * 40)
    push(tmp_path, github, [injection], commit_id="c" * 40)

    assert len(github.reviews) == 1
    [reply] = github.list_replies()
    first_comment_id = github.comments[0].comment_id
    assert reply.in_reply_to_id == first_comment_id
    assert "no longer finds this at bbbbbbb" in reply.body
    assert github.resolved_comment_ids == {first_comment_id}
    assert "replied to 1 gone findings" in summary
    assert "resolved 1 of their threads" in summary


def test_a_thread_the_token_cannot_resolve_still_gets_its_reply(
    tmp_path: Path,
) -> None:
    github = FakeGitHub(can_resolve=False)
    push(tmp_path, github, [build_finding("hardcoded_secrets", "abc123")])
    summary = push(tmp_path, github, [])

    assert len(github.list_replies()) == 1
    assert "could not resolve their threads" in summary


def test_comments_past_the_limit_go_in_the_body_with_a_count(tmp_path: Path) -> None:
    github = FakeGitHub()
    findings = [build_finding(f"rule_{index}", f"{index:012x}") for index in range(53)]
    push(tmp_path, github, findings)

    [review] = github.reviews
    assert len(review.comments) == 50
    assert "**3 more, past the limit of inline comments:**" in review.body


def test_a_refused_line_moves_every_comment_to_the_body(tmp_path: Path) -> None:
    github = FakeGitHub(refused_paths=("app.py",))
    summary = push(tmp_path, github, [build_finding("hardcoded_secrets", "abc123")])

    [review] = github.reviews
    assert review.comments == ()
    assert "<!-- klint-finding:abc123 -->" in review.body
    assert "every finding in its body" in summary


@pytest.mark.parametrize("status", [HTTPStatus.FORBIDDEN, HTTPStatus.NOT_FOUND])
def test_a_token_that_cannot_write_posts_nothing_and_says_so(
    tmp_path: Path, status: HTTPStatus
) -> None:
    github = FakeGitHub(refused_status=status)
    summary = push(tmp_path, github, [build_finding("hardcoded_secrets", "abc123")])

    assert github.reviews == []
    assert "token cannot write" in summary
    assert "`pull-requests: write`" in summary


def test_an_api_error_is_reported_not_raised(tmp_path: Path) -> None:
    github = FakeGitHub(refused_status=HTTPStatus.BAD_GATEWAY)
    summary = push(tmp_path, github, [build_finding("hardcoded_secrets", "abc123")])

    assert "GitHub's API failed" in summary


def test_the_command_without_a_token_posts_nothing_and_passes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    options = [
        "review",
        *("--findings-json", str(tmp_path / "findings.json")),
        *("--diff-file", str(tmp_path / "pr.diff")),
        *("--repository", "owner/name", "--pull-request", "7", "--commit", "abc"),
    ]
    exit_code = asyncio.run(run_pull_request_arguments(options, tmp_path))

    assert exit_code == ExitCode.NO_PROBLEMS
    assert "GITHUB_TOKEN is not set" in capsys.readouterr().out
