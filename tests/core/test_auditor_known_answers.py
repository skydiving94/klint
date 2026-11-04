"""The auditor takes the answers a renderer knows, and asks the judge the rest."""

import asyncio
from collections.abc import Mapping, Sequence

from klint.catalog.domain_neutral import JsonDocumentSourceFactory
from klint.core import Auditor
from klint.core.interfaces import AuditKind, UnitSource
from klint.core.models.audits import AuditInputKind, RenderInput
from klint.core.models.judging import QuestionType
from klint.core.models.reports import AuditReport
from klint.core.models.rules import AuditRule, RuleSet
from klint.core.models.units import UnitTraits
from tests.support.fakes import FakeJudge
from tests.support.notes_suite import (
    POLITE_RULE,
    POLITENESS_SCALE,
    FixedRuleLoader,
    NoteDocumentExtractor,
    NoteRenderer,
    NoteUnit,
)

_SHORT_RULE = AuditRule(
    rule_id="short_note",
    question_type=QuestionType.CHOICE,
    question="Is the note short?",
    unit_types=["note"],
)


class _BlankNoteRenderer(NoteRenderer):
    """Knows that a blank note is rude, and that it is neither short nor long."""

    def find_known_answers(
        self, render_input: RenderInput, rule_ids: Sequence[str]
    ) -> Mapping[str, str | None]:
        if render_input.get_unit_as(NoteUnit).text:
            return {}
        rule_id_to_choice_key: dict[str, str | None] = {
            rule_id: None for rule_id in rule_ids
        }
        rule_id_to_choice_key[POLITE_RULE.rule_id] = "rude"
        return rule_id_to_choice_key


def _audit_notes(judge: FakeJudge, *notes: NoteUnit) -> AuditReport:
    audit_kind = AuditKind(
        kind_id="notes",
        accepted_input_kinds=frozenset({AuditInputKind.IN_MEMORY_BYTES}),
        unit_source=UnitSource(JsonDocumentSourceFactory(), NoteDocumentExtractor()),
        rule_loader=FixedRuleLoader([POLITE_RULE, _SHORT_RULE]),
        answer_scale=POLITENESS_SCALE,
        unit_class_to_renderer={NoteUnit: _BlankNoteRenderer()},
    )
    rule_set = RuleSet({UnitTraits(): [POLITE_RULE, _SHORT_RULE]})
    return asyncio.run(Auditor(judge).audit(notes, rule_set, audit_kind))


def test_a_known_answer_is_a_finding_with_no_confidence_and_no_judge_call() -> None:
    judge = FakeJudge(default="polite")

    report = _audit_notes(judge, NoteUnit(unit_id="blank", text=""))

    (finding,) = report.list_findings()
    assert (finding.rule_id, finding.answer.key) == ("polite_note", "rude")
    assert finding.confidence is None
    assert report.list_audited_unit_ids() == ["blank"]
    assert judge.requests == []


def test_the_judge_is_asked_only_the_rules_no_answer_is_known_for() -> None:
    judge = FakeJudge(default="polite", confidence=0.8)

    report = _audit_notes(
        judge, NoteUnit(unit_id="kind", text="Thanks!"), NoteUnit(unit_id="blank")
    )

    assert [
        (finding.unit_id, finding.rule_id, finding.answer.key, finding.confidence)
        for finding in report.list_findings()
    ] == [
        ("kind", "polite_note", "polite", 0.8),
        ("kind", "short_note", "polite", 0.8),
        ("blank", "polite_note", "rude", None),
    ]
    assert judge.map_subject_to_asked_rule_ids() == {
        "Thanks!": {"polite_note", "short_note"}
    }
