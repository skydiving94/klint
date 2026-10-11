"""Whole-file extraction: one unit per file."""

import asyncio
from pathlib import Path

import pytest

from src.catalog.common.extractors.whole_file import WholeFileExtractor
from src.catalog.common.file_traits_identifiers.extension_identifier import (
    ExtensionFileTraitsIdentifier,
)
from src.catalog.common.units.file import AuditableFileUnit
from tests.support.builders import write_text

EXTRACTOR = WholeFileExtractor(ExtensionFileTraitsIdentifier({".py": "python"}))


def test_whole_file_extractor_returns_one_unit_spanning_the_file(
    tmp_path: Path,
) -> None:
    target = write_text(tmp_path / "a.py", "x = 1\ny = 2\nz = 3\n")

    (unit,) = asyncio.run(EXTRACTOR.extract(target))

    assert isinstance(unit, AuditableFileUnit)
    assert unit.unit_type == "file"
    assert unit.unit_id == str(target)
    assert unit.get_content() == "x = 1\ny = 2\nz = 3\n"
    assert unit.get_metadata() == {"file_path": str(target), "line_range": [1, 3]}


@pytest.mark.parametrize(
    ("file_name", "language"),
    [("a.py", "python"), ("A.PY", "python"), ("a.go", None), ("Makefile", None)],
)
def test_whole_file_unit_carries_the_identified_language(
    tmp_path: Path, file_name: str, language: str | None
) -> None:
    target = write_text(tmp_path / file_name, "x = 1\n")

    (unit,) = asyncio.run(EXTRACTOR.extract(target))

    assert unit.language == language
    assert unit.get_content() == "x = 1\n"
