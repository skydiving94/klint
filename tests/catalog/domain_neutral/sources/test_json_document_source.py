"""A kind of audit that reads one JSON document, from memory or from disk."""

import asyncio
from pathlib import Path

import pytest

from klint.app.pipeline.audit_pipeline import AuditOutcome, AuditRequest
from klint.core.models.audit_input import (
    AuditInput,
    DiskPathInput,
    InMemoryBytesInput,
)
from tests.support.builders import build_audit_pipeline, write_text
from tests.support.fakes import FakeJudge
from tests.support.notes_suite import (
    NOTES_DOCUMENT_KIND_ID,
    add_the_notes_document_suite,
)

NOTES_DOCUMENT = b'{"notes": {"thanks": "Thank you!", "reply": "Go away."}}'


def _run_audit(judge: FakeJudge, audit_input: AuditInput) -> AuditOutcome:
    pipeline = build_audit_pipeline(
        judge, binding_overrides=[add_the_notes_document_suite]
    )
    request = AuditRequest(
        audit_input=audit_input, audit_kind_id=NOTES_DOCUMENT_KIND_ID
    )
    return asyncio.run(pipeline.run_audit(request))


def _answers(outcome: AuditOutcome) -> list[tuple[str, str]]:
    return [
        (finding.unit_id, finding.answer.label)
        for finding in outcome.report.select_findings(should_include_non_problems=True)
    ]


@pytest.mark.parametrize(
    "media_type",
    ["application/json", "application/json; charset=utf-8", "application/notes+json"],
)
def test_json_document_held_in_memory_is_audited_with_no_file(
    fake_judge: type[FakeJudge], media_type: str
) -> None:
    judge = fake_judge(choices={"polite_note": "rude"})

    outcome = _run_audit(
        judge, InMemoryBytesInput(content=NOTES_DOCUMENT, media_type=media_type)
    )

    assert outcome.scanned_file_count == 0
    assert outcome.report.audited_unit_ids() == ["thanks", "reply"]
    assert _answers(outcome) == [("thanks", "Rude"), ("reply", "Rude")]
    assert judge.subject_to_asked_rule_ids() == {
        "Thank you!": {"polite_note"},
        "Go away.": {"polite_note"},
    }


def test_json_document_on_disk_gives_the_same_findings_as_in_memory(
    tmp_path: Path, fake_judge: type[FakeJudge]
) -> None:
    document = write_text(tmp_path / "notes.json", NOTES_DOCUMENT.decode())
    in_memory = InMemoryBytesInput(
        content=NOTES_DOCUMENT, media_type="application/json"
    )

    on_disk_outcome = _run_audit(fake_judge(), DiskPathInput(path=document))
    in_memory_outcome = _run_audit(fake_judge(), in_memory)

    assert on_disk_outcome.scanned_file_count == 1
    assert _answers(on_disk_outcome) == _answers(in_memory_outcome)


def test_content_in_memory_of_another_media_type_is_refused(
    fake_judge: type[FakeJudge],
) -> None:
    judge = fake_judge()

    with pytest.raises(ValueError, match="not 'text/plain'"):
        _run_audit(
            judge, InMemoryBytesInput(content=NOTES_DOCUMENT, media_type="text/plain")
        )

    assert judge.requests == []


def test_content_that_is_not_json_is_refused_before_the_judge_is_asked(
    fake_judge: type[FakeJudge],
) -> None:
    judge = fake_judge()

    with pytest.raises(ValueError, match="The content in memory is not valid JSON"):
        _run_audit(
            judge,
            InMemoryBytesInput(content=b'{"notes": ', media_type="application/json"),
        )

    assert judge.requests == []


def test_content_nested_too_deeply_is_refused_as_unusable(
    fake_judge: type[FakeJudge],
) -> None:
    depth = 100_000
    content = b"[" * depth + b"]" * depth

    with pytest.raises(ValueError, match="nested too deeply to parse"):
        _run_audit(
            fake_judge(),
            InMemoryBytesInput(content=content, media_type="application/json"),
        )


def test_file_that_is_not_json_is_refused_with_its_path(
    tmp_path: Path, fake_judge: type[FakeJudge]
) -> None:
    document = write_text(tmp_path / "notes.json", "notes: none\n")

    with pytest.raises(ValueError, match="is not valid JSON") as raised:
        _run_audit(fake_judge(), DiskPathInput(path=document))

    assert str(document) in str(raised.value)


def test_missing_file_is_raised(tmp_path: Path, fake_judge: type[FakeJudge]) -> None:
    with pytest.raises(FileNotFoundError):
        _run_audit(fake_judge(), DiskPathInput(path=tmp_path / "absent.json"))
