"""A suite and its kind of audit added in test code only, next to the built-in ones."""

import asyncio
import json
from dataclasses import dataclass, replace
from pathlib import Path
from typing import ClassVar

import pytest
from injector import Binder

from klint.app.pipeline.audit_pipeline import AuditOutcome, AuditRequest
from klint.catalog.code import FILE_CONTENTS_KIND_ID
from klint.cli.exit_code import ExitCode
from klint.cli.runner import AuditCommand
from klint.core.interfaces.rule_loader import BaseRuleLoader
from klint.core.interfaces.suite import BaseSuite
from klint.core.interfaces.target_extractor import BaseTargetExtractor
from klint.core.models.audit_kind import AuditKind
from klint.core.models.file_traits import FileTraits
from klint.core.models.ignored_names import IgnoredNames
from klint.core.models.question_type import QuestionType
from klint.core.models.rule import AuditRule
from klint.core.models.scale import AnswerScale, Choice
from klint.core.models.scanned_tree import ScannedTarget
from klint.core.models.unit import AuditableUnit
from klint.core.registry import UnitRegistry
from tests.support.builders import (
    build_audit_command_app,
    build_audit_pipeline,
    write_text,
)
from tests.support.fakes import FakeJudge

NOTES_KIND_ID = "notes"
POLITENESS_SCALE = AnswerScale(
    name="politeness",
    choices=(
        Choice(key="polite", label="Polite", criterion="The note is polite."),
        Choice(
            key="rude", label="Rude", criterion="The note is rude.", is_finding=True
        ),
    ),
)
POLITE_RULE = AuditRule(
    rule_id="polite_note",
    question_type=QuestionType.CHOICE,
    instructions="Is the note polite?",
    target_unit_types=["note"],
)
NOTES_COMMAND = AuditCommand(
    name="klint-notes",
    description="Audits notes",
    target_argument_name="folder",
    target_argument_help="Folder of notes",
    audit_kind_id=NOTES_KIND_ID,
    json_key="examined_notes",
)


@dataclass(frozen=True)
class NoteUnit(AuditableUnit):
    """One note: the text of a .txt file."""

    unit_type: ClassVar[str] = "note"

    text: str = ""

    def get_content(self) -> str:
        return self.text

    def get_metadata(self) -> dict[str, object]:
        return {}


class NoteExtractor(BaseTargetExtractor):
    """Reads each .txt file of a target as one note."""

    async def extract_units(self, scanned_target: ScannedTarget) -> list[AuditableUnit]:
        return [
            NoteUnit(unit_id=str(scanned_file.path), text=scanned_file.path.read_text())
            for scanned_file in scanned_target.files
            if scanned_file.path.suffix == ".txt"
        ]


class FixedRuleLoader(BaseRuleLoader):
    """Gives the same rules for every file; a custom rules file is not read."""

    def __init__(self, rules: list[AuditRule]) -> None:
        self._rules = rules

    async def load_rules(
        self, traits: FileTraits, custom_rules_source: str | Path | None = None
    ) -> list[AuditRule]:
        del traits, custom_rules_source
        return list(self._rules)


class NotesSuite(BaseSuite):
    """Audits notes for politeness; a scan leaves out the drafts folder."""

    def list_audit_kinds(self) -> list[AuditKind]:
        return [
            AuditKind(
                kind_id=NOTES_KIND_ID,
                extractor=NoteExtractor(),
                rule_loader=FixedRuleLoader([POLITE_RULE]),
                answer_scale=POLITENESS_SCALE,
                ignored_names=IgnoredNames(directory_names=frozenset({"drafts"})),
            )
        ]

    def register_unit_types(self, registry: UnitRegistry) -> None:
        registry.register_unit(NoteUnit)


class DuplicateFileContentsSuite(NotesSuite):
    """Offers a kind under an ID the code suite already uses."""

    def list_audit_kinds(self) -> list[AuditKind]:
        (notes_kind,) = super().list_audit_kinds()
        return [replace(notes_kind, kind_id=FILE_CONTENTS_KIND_ID)]


def add_the_notes_suite(binder: Binder) -> None:
    binder.multibind(list[BaseSuite], to=[NotesSuite])


def add_a_suite_with_a_duplicate_kind(binder: Binder) -> None:
    binder.multibind(list[BaseSuite], to=[DuplicateFileContentsSuite])


def _write_notes(folder: Path) -> None:
    write_text(folder / "thanks.txt", "Thank you!\n")
    write_text(folder / "build" / "reply.txt", "Go away.\n")
    write_text(folder / "drafts" / "rant.txt", "Grr.\n")
    write_text(folder / "tool.py", "x = 1\n")


def test_command_for_a_suite_added_in_test_code_runs_end_to_end(
    tmp_path: Path, fake_judge: type[FakeJudge], capsys: pytest.CaptureFixture[str]
) -> None:
    _write_notes(tmp_path)
    judge = fake_judge(default="rude")
    app = build_audit_command_app(NOTES_COMMAND, judge, overrides=[add_the_notes_suite])

    exit_code = asyncio.run(app.run([str(tmp_path), "--json"]))

    output = json.loads(capsys.readouterr().out)
    # The kind ignores drafts/ only: build/ is left out by the code suite's
    # kinds, not by this one.
    notes = [str(tmp_path / "build" / "reply.txt"), str(tmp_path / "thanks.txt")]
    assert exit_code == ExitCode.PROBLEMS_FOUND
    assert output["examined_notes"] == notes
    assert [(issue["unit_id"], issue["judgment"]) for issue in output["issues"]] == [
        (notes[0], "Rude"),
        (notes[1], "Rude"),
    ]
    assert judge.subject_to_asked_rule_ids() == {
        "Go away.\n": {"polite_note"},
        "Thank you!\n": {"polite_note"},
    }


def test_two_kinds_with_different_scales_run_in_one_process(
    tmp_path: Path, fake_judge: type[FakeJudge]
) -> None:
    _write_notes(tmp_path)
    judge = fake_judge(choices={"polite_note": "polite", "tidy_file": "fail"})
    pipeline = build_audit_pipeline(judge, overrides=[add_the_notes_suite])

    def run_audit(audit_kind_id: str) -> AuditOutcome:
        request = AuditRequest(target=tmp_path, audit_kind_id=audit_kind_id)
        return asyncio.run(pipeline.run_audit(request))

    code_outcome = run_audit(FILE_CONTENTS_KIND_ID)
    code_requests = list(judge.requests)
    notes_outcome = run_audit(NOTES_KIND_ID)
    notes_requests = judge.requests[len(code_requests) :]

    code_labels = {
        finding.choice.label
        for finding in code_outcome.report.get_findings(fails_only=False)
    }
    notes_labels = {
        finding.choice.label
        for finding in notes_outcome.report.get_findings(fails_only=False)
    }
    assert (code_labels, notes_labels) == ({"Fail"}, {"Polite"})
    code_criteria = {
        key
        for request in code_requests
        for question in request.questions
        for key in question.choice_key_to_criterion
    }
    notes_criteria = {
        key
        for request in notes_requests
        for question in request.questions
        for key in question.choice_key_to_criterion
    }
    assert code_criteria == {"pass", "fail", "irrelevant", "lack_of_evidence"}
    assert notes_criteria == {"polite", "rude"}
    # Only a problem on the kind's own scale counts as a failure.
    assert code_outcome.report.get_findings()
    assert not notes_outcome.report.get_findings()


def test_two_suites_offering_one_kind_id_stop_the_run_from_being_built(
    fake_judge: type[FakeJudge],
) -> None:
    with pytest.raises(ValueError, match="'file_contents' is offered by two suites"):
        build_audit_pipeline(
            fake_judge(), overrides=[add_a_suite_with_a_duplicate_kind]
        )
