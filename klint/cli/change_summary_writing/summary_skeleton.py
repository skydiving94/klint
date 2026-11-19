"""A summaries-only document shaped like a change, with every summary left empty."""

import json
from pathlib import Path

from klint.catalog.change_summary.documents import (
    SUPPORTED_SCHEMA_VERSION,
    require_changed_files,
)
from klint.catalog.domain_neutral.git import GitChange, GitChangeSource
from klint.cli.change_summary_writing.changed_files import (
    list_changed_files,
    read_change_to_summarize,
)
from klint.core.models.reports import JsonValue


async def build_summary_skeleton(commit: str | None) -> str:
    """Return the skeleton of a change in the current directory's repository, as JSON.

    The change is ``commit``, against its first parent, or the uncommitted
    change when ``commit`` is None. It names the change as klint-change-summary
    reads it, and lists each changed file with its hunks' headers. Each
    summary is null and packages is empty, for the agent to fill in.

    Raises ValueError when the directory is not in a git repository, the
    commit is not known, or the change holds no file.
    """
    source = GitChangeSource(Path.cwd(), commit=commit)
    change = await read_change_to_summarize(source)
    require_changed_files(change)
    return json.dumps(_build_document(change, commit), indent=2)


def _build_document(change: GitChange, commit: str | None) -> JsonValue:
    git_change: JsonValue = {} if commit is None else {"commit": commit}
    files: list[JsonValue] = [
        {
            "path": listed_file.path,
            "summary": None,
            "hunks": [
                {"header": header, "summary": None}
                for header in listed_file.hunk_headers
            ],
        }
        for listed_file in list_changed_files(change)
    ]
    return {
        "schema_version": SUPPORTED_SCHEMA_VERSION,
        "git_change": git_change,
        "summary": None,
        "packages": [],
        "files": files,
    }
