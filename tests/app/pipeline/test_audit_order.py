"""The order a kind of audit judges its units in."""

import pytest

from klint.app.audit_kind_registry import AuditKindRegistry
from klint.catalog.code import FILE_CONTENTS_KIND_ID, PROJECT_STRUCTURE_KIND_ID
from klint.cli.wiring import create_command_injector
from klint.core.models.audit_order import AuditOrder
from tests.support.builders import make_settings
from tests.support.fakes import FakeJudge
from tests.support.outline_suite import SUBJECT_TO_PARENT_SUBJECT, run_outline_audit


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
