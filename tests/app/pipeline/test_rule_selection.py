"""Which rules a run asks about each unit: by unit type, then by its traits."""

import asyncio
from dataclasses import replace
from pathlib import Path

from injector import Binder

from klint.app.pipeline.audit_pipeline import AuditRequest
from klint.core.interfaces.suite import BaseSuite
from klint.core.models.audit_input import DiskPathInput
from klint.core.models.audit_kind import AuditKind
from klint.core.models.question_type import QuestionType
from klint.core.models.rule import AuditRule
from tests.support.builders import build_audit_pipeline, write_text
from tests.support.fakes import FakeJudge
from tests.support.notes_suite import (
    NOTES_KIND_ID,
    POLITE_RULE,
    FixedRuleLoader,
    NotesSuite,
)


def _build_rule(
    rule_id: str, unit_types: list[str], languages: list[str] | None = None
) -> AuditRule:
    return AuditRule(
        rule_id=rule_id,
        question_type=QuestionType.CHOICE,
        question=f"Is {rule_id} kept?",
        unit_types=unit_types,
        languages=languages or [],
    )


class MixedRulesNotesSuite(NotesSuite):
    """Notes asked rules for notes and for files, some limited to a language."""

    def list_audit_kinds(self) -> list[AuditKind]:
        (notes_kind,) = super().list_audit_kinds()
        rules = [
            _build_rule("whole_file_rule", ["file"]),
            POLITE_RULE,
            _build_rule("python_note_rule", ["note"], languages=["python"]),
            _build_rule("short_note", ["note", "file"]),
        ]
        return [replace(notes_kind, rule_loader=FixedRuleLoader(rules))]


def add_the_mixed_rules_notes_suite(binder: Binder) -> None:
    binder.multibind(list[BaseSuite], to=[MixedRulesNotesSuite])


def test_unit_with_no_language_is_asked_the_rules_for_its_unit_type(
    tmp_path: Path, fake_judge: type[FakeJudge]
) -> None:
    write_text(tmp_path / "thanks.txt", "Thank you!\n")
    judge = fake_judge(default="polite")
    pipeline = build_audit_pipeline(
        judge, binding_overrides=[add_the_mixed_rules_notes_suite]
    )

    outcome = asyncio.run(
        pipeline.run_audit(
            AuditRequest(
                audit_input=DiskPathInput(path=tmp_path), audit_kind_id=NOTES_KIND_ID
            )
        )
    )

    # The rule for files is for another unit type, and the rule limited to
    # Python cannot apply to a note in no language.
    assert judge.map_subject_to_asked_rule_ids() == {
        "Thank you!\n": {"polite_note", "short_note"}
    }
    findings = outcome.report.select_findings(should_include_non_problems=True)
    assert [finding.rule_id for finding in findings] == [
        "polite_note",
        "short_note",
    ]
