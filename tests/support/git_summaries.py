"""A greeter repository with an uncommitted change, and summaries of that change."""

import asyncio
import copy
import json
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from klint.cli import CHANGE_SUMMARY_COMMAND, ExitCode
from tests.support.builders import build_audit_command_app
from tests.support.change_summary import HypothesisJudge
from tests.support.git_repository import create_repository, write_files

SummariesData = dict[str, Any]

GREET_BEFORE = "import os\n\n\ndef greet(name):\n    return 'hi'\n"
GREET_AFTER = (
    "\n\ndef greet(name):\n    name = name.strip()\n    return f'Hello, {name}!'\n"
)
GUIDE = "Run greet(name).\n"
# The change: app/greet.py loses an import and greets by the stripped name,
# and the untracked docs/guide.md is added.
GREETER_CHANGE = {"app/greet.py": GREET_AFTER, "docs/guide.md": GUIDE}
IMPORT_HUNK = {"header": "@@ -1 +0,0 @@", "summary": "Removes the unused import of os."}
GREETING_HUNK = {
    "header": "@@ -5 +4,2 @@ def greet(name):",
    "summary": "Strips the name and greets it with 'Hello, <name>!' instead of 'hi'.",
}
GUIDE_HUNK = {"header": "@@ -0,0 +1 @@", "summary": "Says to run greet(name)."}
GREETER_SUMMARIES: SummariesData = {
    "schema_version": 1,
    "git_change": {},
    "summary": "Greets people by their stripped name, and adds a guide.",
    "packages": [
        {"path": "app", "summary": "Greets a stripped name with 'Hello, <name>!'."}
    ],
    "files": [
        {
            "path": "app/greet.py",
            "summary": "Greets a stripped name with 'Hello, <name>!' and drops "
            "an unused import.",
            "hunks": [IMPORT_HUNK, GREETING_HUNK],
        },
        {
            "path": "docs/guide.md",
            "summary": "Adds a guide that says to run greet(name).",
            "hunks": [GUIDE_HUNK],
        },
    ],
}
# Every summary of the greeter change, as unit IDs, in audit report order.
GREETER_UNIT_IDS = [
    "./",
    "app/",
    "app/greet.py",
    "app/greet.py#1",
    "app/greet.py#2",
    "docs/guide.md",
    "docs/guide.md#1",
]


def create_greeter_repository(repository: Path) -> Path:
    """Create the greeter repository, committed, then make its uncommitted change."""
    create_repository(
        repository, {"app/greet.py": GREET_BEFORE, "README.md": "# Greeter\n"}
    )
    write_files(repository, GREETER_CHANGE)
    return repository


def copy_greeter_summaries() -> SummariesData:
    """Return a copy of the greeter summaries that a test may change."""
    return copy.deepcopy(GREETER_SUMMARIES)


def verify_summaries(
    summaries_path: Path,
    judge: HypothesisJudge,
    summaries: object = GREETER_SUMMARIES,
    options: Sequence[str] = ("--json",),
) -> ExitCode:
    """Write ``summaries`` to ``summaries_path`` and run klint-change-summary on it.

    The command prints JSON unless ``options`` say otherwise.
    """
    summaries_path.write_text(json.dumps(summaries), encoding="utf-8")
    app = build_audit_command_app(CHANGE_SUMMARY_COMMAND, judge)
    return asyncio.run(app.run([str(summaries_path), *options]))
