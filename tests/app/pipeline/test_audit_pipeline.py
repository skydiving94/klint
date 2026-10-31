"""The audit use case run on its own, with the fake judge and no command."""

import asyncio
from pathlib import Path

import pytest

from klint.app.pipeline.audit_pipeline import AuditOutcome, AuditRequest
from klint.catalog.code import FILE_CONTENTS_KIND_ID, PROJECT_STRUCTURE_KIND_ID
from klint.core.interfaces.audit_progress_listener import BaseAuditProgressListener
from klint.core.models.audit_input import DiskPathInput, InMemoryBytesInput
from klint.core.models.scale import AnswerChoice
from tests.support.builders import FAIL, PASS, build_audit_pipeline, write_text
from tests.support.fakes import FakeJudge, PickyJudge


class RecordingAuditProgressListener(BaseAuditProgressListener):
    """Writes down every event as one line, in order."""

    def __init__(self) -> None:
        self.events: list[str] = []

    def report_audit_started(self, unit_count: int) -> None:
        self.events.append(f"started {unit_count}")

    def report_unit_audited(self, unit_id: str) -> None:
        self.events.append(f"audited {unit_id}")

    def report_unit_failed(self, unit_id: str, error: Exception) -> None:
        self.events.append(f"failed {unit_id}: {error}")


def _run_audit(judge: FakeJudge, request: AuditRequest) -> AuditOutcome:
    return asyncio.run(build_audit_pipeline(judge).run_audit(request))


def _judgments(outcome: AuditOutcome) -> list[tuple[str, str, AnswerChoice]]:
    return [
        (finding.unit_id, finding.rule_id, finding.answer)
        for finding in outcome.report.select_findings(should_include_non_problems=True)
    ]


def test_file_contents_audit_returns_the_findings_on_each_file(
    tmp_path: Path, fake_judge: type[FakeJudge]
) -> None:
    write_text(tmp_path / "a.py", "x = 1\n")
    write_text(tmp_path / "b.md", "# Notes\n")
    judge = fake_judge(choices={"tidy_file": "fail"})

    outcome = _run_audit(
        judge,
        AuditRequest(
            audit_input=DiskPathInput(tmp_path), audit_kind_id=FILE_CONTENTS_KIND_ID
        ),
    )

    files = (str(tmp_path / "a.py"), str(tmp_path / "b.md"))
    assert outcome.scanned_file_count == 2
    assert outcome.selected_unit_ids == files
    assert outcome.report.audited_unit_ids() == list(files)
    assert _judgments(outcome) == [
        (files[0], "tidy_file", FAIL),
        (files[1], "tidy_file", FAIL),
    ]


def test_project_structure_audit_returns_the_findings_on_each_directory(
    tmp_path: Path, fake_judge: type[FakeJudge]
) -> None:
    write_text(tmp_path / "docs" / "notes.md", "# Notes\n")

    outcome = _run_audit(
        fake_judge(),
        AuditRequest(
            audit_input=DiskPathInput(tmp_path), audit_kind_id=PROJECT_STRUCTURE_KIND_ID
        ),
    )

    directories = (str(tmp_path), str(tmp_path / "docs"))
    assert outcome.scanned_file_count == 1
    assert outcome.selected_unit_ids == directories
    assert _judgments(outcome) == [
        (directories[0], "tidy_directory", PASS),
        (directories[1], "tidy_directory", PASS),
    ]


def test_unit_whose_audit_fails_is_selected_but_left_out_of_the_report(
    tmp_path: Path,
) -> None:
    write_text(tmp_path / "a.py", "x = 1\n")
    write_text(tmp_path / "b.py", "poison\n")
    listener = RecordingAuditProgressListener()

    outcome = _run_audit(
        PickyJudge(refuses="poison"),
        AuditRequest(
            audit_input=DiskPathInput(tmp_path),
            audit_kind_id=FILE_CONTENTS_KIND_ID,
            audit_progress_listener=listener,
        ),
    )

    a_file, b_file = str(tmp_path / "a.py"), str(tmp_path / "b.py")
    assert outcome.selected_unit_ids == (a_file, b_file)
    assert outcome.report.audited_unit_ids() == [a_file]
    assert listener.events[0] == "started 2"
    assert sorted(listener.events[1:]) == [
        f"audited {a_file}",
        f"failed {b_file}: judge is down",
    ]


def test_rules_file_given_with_the_request_is_asked_too(
    tmp_path: Path, fake_judge: type[FakeJudge]
) -> None:
    target = write_text(tmp_path / "a.py", "x = 1\n")
    rules = write_text(
        tmp_path / "rules.json",
        '{"typed": {"type": "choice", "instructions": "Is it typed?"}}',
    )
    judge = fake_judge()

    _run_audit(
        judge,
        AuditRequest(
            audit_input=DiskPathInput(target),
            audit_kind_id=FILE_CONTENTS_KIND_ID,
            custom_rules_source=rules,
        ),
    )

    assert judge.asked_rule_ids() == [["tidy_file", "typed"]]


@pytest.mark.parametrize(
    "audit_kind_id", [FILE_CONTENTS_KIND_ID, PROJECT_STRUCTURE_KIND_ID]
)
def test_missing_target_is_raised_before_the_judge_is_asked(
    tmp_path: Path, fake_judge: type[FakeJudge], audit_kind_id: str
) -> None:
    judge = fake_judge()

    with pytest.raises(FileNotFoundError, match="does not exist"):
        _run_audit(
            judge,
            AuditRequest(
                audit_input=DiskPathInput(tmp_path / "absent"),
                audit_kind_id=audit_kind_id,
            ),
        )

    assert judge.requests == []


def test_unknown_kind_of_audit_is_raised_with_the_known_ones(
    tmp_path: Path, fake_judge: type[FakeJudge]
) -> None:
    write_text(tmp_path / "a.py", "x = 1\n")
    judge = fake_judge()

    with pytest.raises(ValueError, match="Unknown audit kind 'spelling'") as raised:
        _run_audit(
            judge,
            AuditRequest(audit_input=DiskPathInput(tmp_path), audit_kind_id="spelling"),
        )

    assert f"'{FILE_CONTENTS_KIND_ID}'" in str(raised.value)
    assert f"'{PROJECT_STRUCTURE_KIND_ID}'" in str(raised.value)
    assert judge.requests == []


@pytest.mark.parametrize(
    "audit_kind_id", [FILE_CONTENTS_KIND_ID, PROJECT_STRUCTURE_KIND_ID]
)
def test_content_in_memory_is_refused_by_a_kind_that_reads_disk_paths(
    fake_judge: type[FakeJudge], audit_kind_id: str
) -> None:
    judge = fake_judge()
    request = AuditRequest(
        audit_input=InMemoryBytesInput(content=b"x = 1\n", media_type="text/x-python"),
        audit_kind_id=audit_kind_id,
    )

    with pytest.raises(ValueError, match="takes \\['disk_path'\\] input") as raised:
        _run_audit(judge, request)

    assert str(raised.value) == (
        f"The '{audit_kind_id}' audit takes ['disk_path'] input, not 'in_memory_bytes'"
    )
    assert judge.requests == []
