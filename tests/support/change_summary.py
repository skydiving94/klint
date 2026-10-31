"""Change-summary documents for tests, and a way to extract their units."""

import asyncio
import copy
import json
from typing import Any

from klint.app.pipeline.audit_pipeline import AuditOutcome, AuditRequest
from klint.catalog.change_summary import CHANGE_SUMMARY_KIND_ID
from klint.catalog.change_summary.extraction.change_summary_extractor import (
    ChangeSummaryExtractor,
)
from klint.core.models.audit_input import InMemoryBytesInput
from klint.core.models.json_value import JsonValue
from klint.core.models.judge_exchange import JudgeAnswer, JudgeRequest
from klint.core.models.unit import AuditableUnit
from tests.support.builders import build_audit_pipeline
from tests.support.fakes import FakeJudge

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


# The line of a judge's subject that holds the summary judged.
HYPOTHESIS_PREFIX = "Hypothesis: "


class HypothesisJudge(FakeJudge):
    """Answers by what the hypothesis, the summary judged, says.

    For a hypothesis that holds a phrase in ``phrase_to_rule_id_to_choice``,
    each rule named under it gets the choice given; every other question
    is answered "accurate". A hypothesis that holds one of
    ``refused_phrases`` makes the judge fail, as when it is down.
    """

    def __init__(
        self,
        phrase_to_rule_id_to_choice: dict[str, dict[str, str]] | None = None,
        refused_phrases: frozenset[str] = frozenset(),
    ) -> None:
        super().__init__(default="accurate")
        self.phrase_to_rule_id_to_choice = phrase_to_rule_id_to_choice or {}
        self.refused_phrases = refused_phrases

    async def answer(self, request: JudgeRequest) -> list[JudgeAnswer]:
        hypothesis = request.subject.rsplit(HYPOTHESIS_PREFIX, 1)[-1]
        if any(phrase in hypothesis for phrase in self.refused_phrases):
            self.requests.append(request)
            raise RuntimeError("judge is down")
        self.choices = {}
        for phrase, rule_id_to_choice in self.phrase_to_rule_id_to_choice.items():
            if phrase in hypothesis:
                self.choices.update(rule_id_to_choice)
        return await super().answer(request)

    def list_hypotheses(self) -> list[str]:
        """Return the summary judged in each request, in request order."""
        return [
            request.subject.rsplit(HYPOTHESIS_PREFIX, 1)[-1]
            for request in self.requests
        ]

    def find_subject(self, hypothesis: str) -> str:
        """Return the subject the judge read about the summary ``hypothesis``."""
        (subject,) = [
            request.subject
            for request in self.requests
            if request.subject.endswith(f"{HYPOTHESIS_PREFIX}{hypothesis}")
        ]
        return subject


def run_change_summary_audit(
    judge: FakeJudge,
    document: JsonValue = GREETING_DOCUMENT,
    min_confidence: float = 0.0,
) -> AuditOutcome:
    """Verify ``document``, held in memory, with klint's change-summary audit."""
    request = AuditRequest(
        audit_input=InMemoryBytesInput(
            content=json.dumps(document).encode(), media_type="application/json"
        ),
        audit_kind_id=CHANGE_SUMMARY_KIND_ID,
        min_confidence=min_confidence,
    )
    return asyncio.run(build_audit_pipeline(judge).run_audit(request))
