"""A suite and its kind of audit added in test code only, next to the built-in ones."""

import asyncio
import json
from dataclasses import replace
from pathlib import Path

import pytest
from injector import Binder

from klint.app.pipeline.audit_pipeline import AuditOutcome, AuditRequest
from klint.catalog.code import FILE_CONTENTS_KIND_ID
from klint.cli.exit_code import ExitCode
from klint.core.interfaces.suite import BaseSuite
from klint.core.models.audit_input import DiskPathInput
from klint.core.models.audit_kind import AuditKind
from tests.support.builders import (
    build_audit_command_app,
    build_audit_pipeline,
    write_text,
)
from tests.support.fakes import FakeJudge
from tests.support.notes_suite import (
    NOTES_COMMAND,
    NOTES_KIND_ID,
    NotesSuite,
    add_the_notes_suite,
)


class DuplicateFileContentsSuite(NotesSuite):
    """Offers a kind under an ID the code suite already uses."""

    def list_audit_kinds(self) -> list[AuditKind]:
        (notes_kind,) = super().list_audit_kinds()
        return [replace(notes_kind, kind_id=FILE_CONTENTS_KIND_ID)]


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
    app = build_audit_command_app(
        NOTES_COMMAND, judge, binding_overrides=[add_the_notes_suite]
    )

    exit_code = asyncio.run(app.run([str(tmp_path), "--json"]))

    output = json.loads(capsys.readouterr().out)
    # The kind ignores drafts/ only: build/ is left out by the code suite's
    # kinds, not by this one.
    notes = [str(tmp_path / "build" / "reply.txt"), str(tmp_path / "thanks.txt")]
    assert exit_code == ExitCode.PROBLEMS_FOUND
    assert output["examined_notes"] == notes
    assert [(issue["unit_id"], issue["answer"]) for issue in output["findings"]] == [
        (notes[0], "Rude"),
        (notes[1], "Rude"),
    ]
    assert judge.map_subject_to_asked_rule_ids() == {
        "Go away.\n": {"polite_note"},
        "Thank you!\n": {"polite_note"},
    }


def test_two_kinds_with_different_scales_run_in_one_process(
    tmp_path: Path, fake_judge: type[FakeJudge]
) -> None:
    _write_notes(tmp_path)
    judge = fake_judge(choices={"polite_note": "polite", "tidy_file": "fail"})
    pipeline = build_audit_pipeline(judge, binding_overrides=[add_the_notes_suite])

    def run_audit(audit_kind_id: str) -> AuditOutcome:
        request = AuditRequest(
            audit_input=DiskPathInput(tmp_path), audit_kind_id=audit_kind_id
        )
        return asyncio.run(pipeline.run_audit(request))

    code_outcome = run_audit(FILE_CONTENTS_KIND_ID)
    code_requests = list(judge.requests)
    notes_outcome = run_audit(NOTES_KIND_ID)
    notes_requests = judge.requests[len(code_requests) :]

    code_labels = {
        finding.answer.label
        for finding in code_outcome.report.select_findings(
            should_include_non_problems=True
        )
    }
    notes_labels = {
        finding.answer.label
        for finding in notes_outcome.report.select_findings(
            should_include_non_problems=True
        )
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
    assert code_outcome.report.select_findings()
    assert not notes_outcome.report.select_findings()


def test_two_suites_offering_one_kind_id_stop_the_run_from_being_built(
    fake_judge: type[FakeJudge],
) -> None:
    with pytest.raises(ValueError, match="'file_contents' is offered more than once"):
        build_audit_pipeline(
            fake_judge(), binding_overrides=[add_a_suite_with_a_duplicate_kind]
        )
