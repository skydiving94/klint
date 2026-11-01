"""The order a run's report lists its findings in, defined once."""

import asyncio
from dataclasses import replace
from pathlib import Path

from injector import Binder

from klint.app.pipeline.audit_pipeline import AuditOutcome, AuditRequest
from klint.catalog.code import FILE_CONTENTS_KIND_ID
from klint.core.interfaces.suite import BaseSuite
from klint.core.models.audit_input import DiskPathInput
from klint.core.models.audit_kind import AuditKind
from klint.core.models.question_type import QuestionType
from klint.core.models.rule import AuditRule
from tests.support.builders import (
    FILE_RULE,
    build_audit_pipeline,
    make_settings,
    write_json,
    write_text,
)
from tests.support.fakes import FakeJudge
from tests.support.notes_suite import NOTES_KIND_ID, FixedRuleLoader, NotesSuite


def _note_rule(rule_id: str, *tags: str) -> AuditRule:
    return AuditRule(
        rule_id=rule_id,
        question_type=QuestionType.CHOICE,
        question=f"Is {rule_id} kept?",
        target_unit_types=["note"],
        tags=list(tags),
    )


class RankedNotesSuite(NotesSuite):
    """Notes whose security findings come first, then those on tone."""

    def list_audit_kinds(self) -> list[AuditKind]:
        (notes_kind,) = super().list_audit_kinds()
        rules = [
            _note_rule("a_tone", "tone"),
            _note_rule("b_secret", "style", "security"),
            _note_rule("c_plain"),
            _note_rule("d_style", "style"),
            _note_rule("e_polite_secret", "security"),
        ]
        return [
            replace(
                notes_kind,
                rule_loader=FixedRuleLoader(rules),
                ranked_tags=("security", "tone"),
            )
        ]


def add_the_ranked_notes_suite(binder: Binder) -> None:
    binder.multibind(list[BaseSuite], to=[RankedNotesSuite])


def _run_audit(
    judge: FakeJudge, target: Path, audit_kind_id: str, rules: Path | None = None
) -> AuditOutcome:
    settings = make_settings() if rules is None else make_settings([rules], [rules])
    pipeline = build_audit_pipeline(
        judge, settings, binding_overrides=[add_the_ranked_notes_suite]
    )
    request = AuditRequest(
        audit_input=DiskPathInput(target), audit_kind_id=audit_kind_id
    )
    return asyncio.run(pipeline.run_audit(request))


def _ranked(outcome: AuditOutcome) -> list[tuple[str, str]]:
    return [
        (Path(finding.unit_id).name, finding.rule_id)
        for finding in outcome.report.select_findings(should_include_non_problems=True)
    ]


def test_findings_come_by_answer_then_confidence_then_rule_id(
    tmp_path: Path, fake_judge: type[FakeJudge]
) -> None:
    rule_id_to_answer_and_confidence = {
        "p": ("pass", 0.9),
        "i": ("irrelevant", 0.9),
        "f_low": ("fail", 0.3),
        "l": ("lack_of_evidence", 0.9),
        "f_b": ("fail", 0.7),
        "f_a": ("fail", 0.7),
    }
    rules = write_json(
        tmp_path / "rules.json",
        {rule_id: FILE_RULE for rule_id in rule_id_to_answer_and_confidence},
    )
    target = write_text(tmp_path / "a.py", "x = 1\n")
    judge = fake_judge(
        choices={
            rule_id: answer
            for rule_id, (answer, _) in rule_id_to_answer_and_confidence.items()
        },
        rule_id_to_confidence={
            rule_id: confidence
            for rule_id, (_, confidence) in rule_id_to_answer_and_confidence.items()
        },
    )

    outcome = _run_audit(judge, target, FILE_CONTENTS_KIND_ID, rules)

    assert [rule_id for _, rule_id in _ranked(outcome)] == [
        "f_a",
        "f_b",
        "f_low",
        "l",
        "p",
        "i",
    ]


def test_findings_on_one_unit_stay_together_in_audit_order(
    tmp_path: Path, fake_judge: type[FakeJudge]
) -> None:
    rules = write_json(tmp_path / "rules.json", {"r1": FILE_RULE, "r2": FILE_RULE})
    target = tmp_path / "src"
    write_text(target / "a.py", "a = 1\n")
    write_text(target / "b.py", "b = 2\n")
    judge = fake_judge(default="fail", rule_id_to_confidence={"r1": 0.3, "r2": 0.9})

    outcome = _run_audit(judge, target, FILE_CONTENTS_KIND_ID, rules)

    assert _ranked(outcome) == [
        ("a.py", "r2"),
        ("a.py", "r1"),
        ("b.py", "r2"),
        ("b.py", "r1"),
    ]


def test_kind_ranks_findings_by_its_tags_within_an_answer(
    tmp_path: Path, fake_judge: type[FakeJudge]
) -> None:
    write_text(tmp_path / "note.txt", "Hi.\n")
    judge = fake_judge(default="rude", choices={"e_polite_secret": "polite"})

    outcome = _run_audit(judge, tmp_path, NOTES_KIND_ID)

    # A ranked tag counts by the best one a finding has; findings with none
    # come after; a problem comes before any other answer, whatever its tags.
    assert [rule_id for _, rule_id in _ranked(outcome)] == [
        "b_secret",
        "a_tone",
        "c_plain",
        "d_style",
        "e_polite_secret",
    ]
    rule_id_to_tags = {
        finding.rule_id: finding.tags
        for finding in outcome.report.select_findings(should_include_non_problems=True)
    }
    assert rule_id_to_tags["b_secret"] == ("style", "security")
    assert rule_id_to_tags["c_plain"] == ()
