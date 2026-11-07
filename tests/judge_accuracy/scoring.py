"""Case sets for tests of the change-summary scoring command, and a way to run it."""

import asyncio
import json
from pathlib import Path
from typing import Any

from judge_accuracy.change_summary.scoring_command import (
    ScoringExitCode,
    run_scoring,
)
from klint.core.interfaces import BaseJudge
from tests.support.builders import write_text
from tests.support.change_summary import (
    APP_PACKAGE_POINTER,
    GREET_FILE_POINTER,
    GREETING_DOCUMENT,
)
from tests.support.fakes import JudgeBindingOverride

PlantedMistakeData = dict[str, str]

# A true summary of the greeting document, the import hunk's, and a false
# one in its place: the import removed is os, not sys.
IMPORT_HUNK_POINTER = f"{GREET_FILE_POINTER}/hunks/1/summary"
FALSE_IMPORT_SUMMARY = "Removes the unused import of sys."
FALSE_IMPORT_MISTAKE: PlantedMistakeData = {
    "summary_pointer": IMPORT_HUNK_POINTER,
    "mistake_kind": "false_statement",
    "summary": FALSE_IMPORT_SUMMARY,
    "why_wrong": "The import removed is os.",
}
# A package summary that gives a reason nothing in the change states.
REASON_SUMMARY = "Greets a stripped name with 'Hello, <name>!', as users asked."
REASON_MISTAKE: PlantedMistakeData = {
    "summary_pointer": f"{APP_PACKAGE_POINTER}/summary",
    "mistake_kind": "unsupported_reason",
    "summary": REASON_SUMMARY,
    "why_wrong": "No summary below says that users asked.",
}


def write_case_file(
    folder: Path,
    name: str,
    *planted_mistakes: PlantedMistakeData,
    true_document: dict[str, Any] = GREETING_DOCUMENT,
) -> Path:
    """Write a case file of ``true_document`` and ``planted_mistakes``."""
    return write_text(
        folder / f"{name}.json",
        json.dumps(
            {
                "schema_version": 1,
                "true_document": true_document,
                "planted_mistakes": list(planted_mistakes),
            }
        ),
    )


def run_scoring_command(judge: BaseJudge, *arguments: str | Path) -> ScoringExitCode:
    """Run the scoring command with ``arguments``, asking ``judge``."""
    return asyncio.run(
        run_scoring(
            [str(argument) for argument in arguments], JudgeBindingOverride(judge)
        )
    )


def find_table_row(report: str, first_cell: str) -> list[str]:
    """Return the cells of the report's table row whose first cell is ``first_cell``."""
    for line in report.splitlines():
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        if line.startswith("|") and cells[0] == first_cell:
            return cells
    raise AssertionError(f"No table row starts with {first_cell!r}")
