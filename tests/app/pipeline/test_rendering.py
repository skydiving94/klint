"""What the judge reads about each unit, as the renderers of its kind write it."""

import asyncio
import json
import re
from dataclasses import replace
from pathlib import Path

import pytest
from injector import Binder

from klint.app.audit_kind_registry import AuditKindRegistry
from klint.app.pipeline.audit_pipeline import AuditRequest
from klint.catalog.code import FILE_CONTENTS_KIND_ID, PROJECT_STRUCTURE_KIND_ID
from klint.cli.wiring import create_command_injector
from klint.core.interfaces.suite import BaseSuite
from klint.core.models.audit_input import InMemoryBytesInput
from klint.core.models.audit_kind import AuditKind
from tests.support.builders import (
    build_audit_pipeline,
    list_judge_subjects,
    make_settings,
    write_text,
)
from tests.support.fakes import FakeJudge, SubjectJudge
from tests.support.outline_suite import (
    OUTLINE,
    SUMMARIZED_OUTLINE_KIND_ID,
    OutlineSuite,
    run_outline_audit,
)

UNRENDERED_OUTLINE_KIND_ID = "unrendered_outline"


def _map_first_line_to_subject(judge: SubjectJudge) -> dict[str, str]:
    return {
        request.subject.splitlines()[0]: request.subject for request in judge.requests
    }


def test_parent_renderer_receives_the_findings_on_its_children() -> None:
    judge = SubjectJudge({"Section 1.1.": "fail"})

    run_outline_audit(judge, audit_kind_id=SUMMARIZED_OUTLINE_KIND_ID)

    first_line_to_subject = _map_first_line_to_subject(judge)
    assert first_line_to_subject["Chapter 1."] == (
        "Chapter 1.\n"
        "section 1.1: clear_section = fail\n"
        "section 1.2: clear_section = pass"
    )
    # Only the sections directly inside: the book does not see section 1.1.
    assert first_line_to_subject["The book."] == (
        "The book.\nchapter 1: clear_section = pass\nchapter 2: clear_section = pass"
    )
    assert first_line_to_subject["Section 1.1."] == "Section 1.1."


def test_child_whose_audit_failed_gives_its_parent_no_findings() -> None:
    judge = SubjectJudge({}, refused_subjects=frozenset({"Section 1.1."}))

    run_outline_audit(judge, audit_kind_id=SUMMARIZED_OUTLINE_KIND_ID)

    assert _map_first_line_to_subject(judge)["Chapter 1."] == (
        "Chapter 1.\nsection 1.2: clear_section = pass"
    )


def _read_left_out_count(trimming_line: str) -> int:
    match = re.fullmatch(
        r"\[\.\.\. (?:the rest of the line above and )?(\d+) more lines of .+ "
        r"left out to stay within 2000 characters\]",
        trimming_line,
    )
    assert match is not None, trimming_line
    return int(match.group(1))


@pytest.mark.parametrize(
    "audit_kind_id", [FILE_CONTENTS_KIND_ID, PROJECT_STRUCTURE_KIND_ID]
)
def test_built_in_kinds_keep_what_the_judge_reads_within_2000_characters(
    audit_kind_id: str,
) -> None:
    registry = create_command_injector(make_settings()).get(AuditKindRegistry)

    assert registry.find_audit_kind(audit_kind_id).character_budget == 2000


def _find_directory_subject(subjects: list[str], directory: Path) -> str:
    """Return the subject whose first line names ``directory`` as the target."""
    (subject,) = [
        subject
        for subject in subjects
        if subject.splitlines()[0]
        .removeprefix("Target Directory Under Audit: ")
        .split(" (package name: ")[0]
        == str(directory)
    ]
    return subject


@pytest.mark.parametrize("extension", ["py", "md"])
def test_deep_tree_stays_within_budget_and_ends_with_what_it_left_out(
    tmp_path: Path, extension: str
) -> None:
    root = tmp_path / "deep"
    directory = root
    for depth in range(12):
        for index in range(3):
            write_text(directory / f"module_{index}.{extension}", "import os\n")
        deepest = directory
        directory = directory / f"level_{depth}"

    subjects = list_judge_subjects(root, PROJECT_STRUCTURE_KIND_ID)

    root_subject = _find_directory_subject(subjects, root)
    assert len(root_subject) <= 2000
    trimming_line = root_subject.splitlines()[-1]
    assert _read_left_out_count(trimming_line) > 0
    assert "lines of the tree" in trimming_line
    # The deepest directory holds little enough to be shown whole.
    assert not _find_directory_subject(subjects, deepest).endswith(" characters]")


def test_long_file_is_shown_from_its_first_line_as_far_as_the_budget_goes(
    tmp_path: Path,
) -> None:
    content = "".join(f"value_{index} = {index}\n" for index in range(300))
    target = write_text(tmp_path / "long.py", content)

    (subject,) = list_judge_subjects(target, FILE_CONTENTS_KIND_ID)

    assert len(subject) <= 2000
    *kept_lines, trimming_line = subject.split("\n")
    assert kept_lines == content.split("\n")[: len(kept_lines)]
    assert len(kept_lines) + _read_left_out_count(trimming_line) == len(
        content.split("\n")
    )


def test_file_of_exactly_the_budget_is_shown_whole(tmp_path: Path) -> None:
    content = ("x" * 99 + "\n") * 20
    target = write_text(tmp_path / "exact.py", content)

    assert list_judge_subjects(target, FILE_CONTENTS_KIND_ID) == [content]


def test_line_too_long_for_the_budget_is_cut(tmp_path: Path) -> None:
    content = "x" * 5000 + "\ny = 1\n"
    target = write_text(tmp_path / "minified.js", content)

    (subject,) = list_judge_subjects(target, FILE_CONTENTS_KIND_ID)

    first_line, trimming_line = subject.split("\n")
    assert len(subject) <= 2000
    assert content.startswith(first_line)
    assert "the rest of the line above and 2 more lines" in trimming_line


class UnrenderedOutlineSuite(OutlineSuite):
    """Offers the outline audit with no renderer for its sections."""

    def list_audit_kinds(self) -> list[AuditKind]:
        outline_kind, *_ = super().list_audit_kinds()
        return [
            replace(
                outline_kind,
                kind_id=UNRENDERED_OUTLINE_KIND_ID,
                unit_class_to_renderer={},
            )
        ]


def test_kind_with_no_renderer_for_a_unit_fails_before_the_judge_is_asked(
    fake_judge: type[FakeJudge],
) -> None:
    judge = fake_judge()

    def add_the_unrendered_outline_suite(binder: Binder) -> None:
        binder.multibind(list[BaseSuite], to=[UnrenderedOutlineSuite])

    pipeline = build_audit_pipeline(judge, overrides=[add_the_unrendered_outline_suite])
    request = AuditRequest(
        audit_input=InMemoryBytesInput(
            content=json.dumps(OUTLINE).encode(), media_type="application/json"
        ),
        audit_kind_id=UNRENDERED_OUTLINE_KIND_ID,
    )

    with pytest.raises(ValueError, match="no renderer for OutlineSectionUnit units"):
        asyncio.run(pipeline.run_audit(request))
    assert judge.requests == []
