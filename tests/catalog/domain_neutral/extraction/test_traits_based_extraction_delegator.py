"""The start of each file is read once; its extractor is told if it is binary."""

import asyncio
from pathlib import Path

import pytest
from injector import Binder

from klint.catalog.code import FILE_CONTENTS_KIND_ID, PROJECT_STRUCTURE_KIND_ID
from klint.catalog.domain_neutral.extraction import traits_based_extraction_delegator
from klint.catalog.domain_neutral.extraction.dispatched_file import DispatchedFile
from klint.catalog.domain_neutral.extraction.file_start import read_file_start
from klint.cli.file_audit import FILE_AUDIT_COMMAND
from klint.core.interfaces.extractor import BaseUnitExtractor
from klint.core.models.unit import AuditableUnit
from tests.support.builders import (
    build_audit_command_app,
    list_judge_subjects,
    write_text,
)
from tests.support.fakes import FakeJudge


def _write_text_and_binary_files(folder: Path) -> list[Path]:
    """Write a Python file, a text file and a binary file; return their paths."""
    binary = folder / "pkg" / "logo.py"
    paths = [
        write_text(folder / "pkg" / "a.py", "import os\n"),
        write_text(folder / "pkg" / "notes.txt", "Hello.\n"),
        binary,
    ]
    binary.write_bytes(b"\x00\x01\n")
    return paths


@pytest.mark.parametrize(
    "audit_kind_id", [FILE_CONTENTS_KIND_ID, PROJECT_STRUCTURE_KIND_ID]
)
def test_the_start_of_each_file_is_read_once(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, audit_kind_id: str
) -> None:
    paths = _write_text_and_binary_files(tmp_path)
    checked_paths: list[Path] = []

    def read_and_record(path: Path) -> bytes:
        checked_paths.append(path)
        return read_file_start(path)

    monkeypatch.setattr(
        traits_based_extraction_delegator, "read_file_start", read_and_record
    )

    list_judge_subjects(tmp_path / "pkg", audit_kind_id)

    assert sorted(checked_paths) == sorted(paths)


class RecordingExtractor(BaseUnitExtractor[DispatchedFile]):
    """Records the files it is handed, and extracts no unit from them."""

    def __init__(self) -> None:
        self.dispatched_files: list[DispatchedFile] = []

    async def extract(self, audit_input: DispatchedFile) -> list[AuditableUnit]:
        self.dispatched_files.append(audit_input)
        return []


def test_extractor_is_told_whether_its_file_is_binary(tmp_path: Path) -> None:
    text_file, _, binary_file = _write_text_and_binary_files(tmp_path)
    recording_extractor = RecordingExtractor()

    def use_the_recording_extractor_for_python(binder: Binder) -> None:
        binder.multibind(
            dict[str, BaseUnitExtractor[DispatchedFile]],
            to=lambda: {"python": recording_extractor},
        )

    app = build_audit_command_app(
        FILE_AUDIT_COMMAND,
        FakeJudge(),
        binding_overrides=[use_the_recording_extractor_for_python],
    )

    asyncio.run(app.run([str(tmp_path / "pkg"), "--json"]))

    assert {
        dispatched_file.path: dispatched_file.is_binary
        for dispatched_file in recording_extractor.dispatched_files
    } == {text_file: False, binary_file: True}
