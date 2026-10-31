"""The order a kind of audit judges its units in."""

import asyncio
import json

import pytest

from klint.app.audit_kind_registry import AuditKindRegistry
from klint.app.pipeline.audit_pipeline import AuditOutcome, AuditRequest
from klint.catalog.code import FILE_CONTENTS_KIND_ID, PROJECT_STRUCTURE_KIND_ID
from klint.cli.wiring import create_command_injector
from klint.core.models.audit_input import InMemoryBytesInput
from klint.core.models.audit_order import AuditOrder
from tests.support.builders import build_audit_pipeline, make_settings
from tests.support.fakes import FakeJudge
from tests.support.outline_suite import OUTLINE_KIND_ID, add_the_outline_suite

# A three-level outline: the book, its chapters, and their sections.
OUTLINE = {
    "id": "book",
    "text": "The book.",
    "sections": [
        {
            "id": "chapter 1",
            "text": "Chapter 1.",
            "sections": [
                {"id": "section 1.1", "text": "Section 1.1."},
                {"id": "section 1.2", "text": "Section 1.2."},
            ],
        },
        {
            "id": "chapter 2",
            "text": "Chapter 2.",
            "sections": [{"id": "section 2.1", "text": "Section 2.1."}],
        },
    ],
}
SUBJECT_TO_PARENT_SUBJECT = {
    "Chapter 1.": "The book.",
    "Chapter 2.": "The book.",
    "Section 1.1.": "Chapter 1.",
    "Section 1.2.": "Chapter 1.",
    "Section 2.1.": "Chapter 2.",
}


def run_outline_audit(judge: FakeJudge, outline: object = OUTLINE) -> AuditOutcome:
    """Audit ``outline``, held in memory, with the outline suite."""
    pipeline = build_audit_pipeline(judge, overrides=[add_the_outline_suite])
    request = AuditRequest(
        audit_input=InMemoryBytesInput(
            content=json.dumps(outline).encode(), media_type="application/json"
        ),
        audit_kind_id=OUTLINE_KIND_ID,
    )
    return asyncio.run(pipeline.run_audit(request))


def test_children_first_judges_every_child_before_its_parent(
    fake_judge: type[FakeJudge],
) -> None:
    judge = fake_judge()

    outcome = run_outline_audit(judge)

    subjects_in_judged_order = [request.subject for request in judge.requests]
    assert sorted(subjects_in_judged_order) == sorted(
        [*SUBJECT_TO_PARENT_SUBJECT, "The book."]
    )
    for child, parent in SUBJECT_TO_PARENT_SUBJECT.items():
        assert subjects_in_judged_order.index(child) < subjects_in_judged_order.index(
            parent
        ), (child, parent)
    # The report keeps the outline's own order, each section before its own.
    assert outcome.report.audited_unit_ids() == [
        "book",
        "chapter 1",
        "section 1.1",
        "section 1.2",
        "chapter 2",
        "section 2.1",
    ]


@pytest.mark.parametrize(
    "audit_kind_id", [FILE_CONTENTS_KIND_ID, PROJECT_STRUCTURE_KIND_ID]
)
def test_built_in_kinds_judge_all_their_units_at_once(audit_kind_id: str) -> None:
    registry = create_command_injector(make_settings()).get(AuditKindRegistry)

    audit_kind = registry.find_audit_kind(audit_kind_id)

    assert audit_kind.audit_order is AuditOrder.ALL_AT_ONCE
