"""Change-summary documents for tests, and a way to extract their units."""

import asyncio
import copy
from typing import Any

from klint.catalog.change_summary.extraction.change_summary_extractor import (
    ChangeSummaryExtractor,
)
from klint.core.models.json_value import JsonValue
from klint.core.models.unit import AuditableUnit

ChangeSummaryDocumentData = dict[str, Any]

# A small change: one file changed in the package "app", one file added at
# the root. The summary of each level is true of the level below.
GREETING_HUNK = {
    "hunk_id": "app/greet.py#1",
    "old_start": 3,
    "old_line_count": 1,
    "new_start": 3,
    "new_line_count": 2,
    "removed_lines": ["    return 'hi'"],
    "added_lines": ["    name = name.strip()", "    return f'Hello, {name}!'"],
    "summary": "Strips the name and greets it with 'Hello, <name>!' instead of 'hi'.",
}
REMOVED_IMPORT_HUNK = {
    "hunk_id": "app/greet.py#2",
    "old_start": 1,
    "old_line_count": 1,
    "new_start": 0,
    "new_line_count": 0,
    "removed_lines": ["import os"],
    "added_lines": [],
    "summary": "Removes the unused import of os.",
}
README_HUNK = {
    "hunk_id": "README.md#1",
    "old_start": 0,
    "old_line_count": 0,
    "new_start": 1,
    "new_line_count": 2,
    "removed_lines": [],
    "added_lines": ["# Greeter", "Greets people by name."],
    "summary": "Adds a title and a one-line description of the greeter.",
}
GREETING_DOCUMENT: ChangeSummaryDocumentData = {
    "schema_version": 1,
    "diff_command": "git diff HEAD -U0; git ls-files --others --exclude-standard",
    "root_package": {
        "path": ".",
        "summary": "Greets people by their stripped name, and adds a README.",
        "packages": [
            {
                "path": "app",
                "summary": "Greets a stripped name with 'Hello, <name>!'.",
                "packages": [],
                "files": [
                    {
                        "path": "app/greet.py",
                        "old_path": None,
                        "change_kind": "modified",
                        "summary": "Greets a stripped name with 'Hello, <name>!' "
                        "and drops an unused import.",
                        "hunks": [GREETING_HUNK, REMOVED_IMPORT_HUNK],
                    }
                ],
            }
        ],
        "files": [
            {
                "path": "README.md",
                "old_path": None,
                "change_kind": "added",
                "summary": "Adds a README that names and describes the greeter.",
                "hunks": [README_HUNK],
            }
        ],
    },
}
# Where the parts of the greeting document sit, as JSON pointers.
APP_PACKAGE_POINTER = "#/root_package/packages/0"
GREET_FILE_POINTER = f"{APP_PACKAGE_POINTER}/files/0"
README_FILE_POINTER = "#/root_package/files/0"


def copy_greeting_document() -> ChangeSummaryDocumentData:
    """Return a copy of the greeting document that a test may change."""
    return copy.deepcopy(GREETING_DOCUMENT)


def extract_summary_units(document: JsonValue) -> list[AuditableUnit]:
    """Return the units the change-summary extractor reads from ``document``."""
    return asyncio.run(ChangeSummaryExtractor().extract(document))
