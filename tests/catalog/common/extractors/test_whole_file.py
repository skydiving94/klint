"""Whole-file extraction: one unit per file."""

import asyncio
from pathlib import Path

import pytest

from klint.catalog.common.extractors.whole_file import WholeFileExtractor
from klint.catalog.common.units.file import AuditableFileUnit
from klint.core.models.file_traits import FileTraits
from klint.core.models.location import Location
from klint.core.models.scanned_tree import ScannedFile
from klint.core.models.unit import AuditableUnit, UnitContext
from tests.support.builders import write_text


def _extract(path: Path, language: str | None = None) -> list[AuditableUnit]:
    scanned_file = ScannedFile(path=path, traits=FileTraits(language=language))
    return asyncio.run(WholeFileExtractor().extract(scanned_file))


def test_whole_file_extractor_returns_one_unit_spanning_the_file(
    tmp_path: Path,
) -> None:
    target = write_text(tmp_path / "a.py", "x = 1\ny = 2\nz = 3\n")

    (unit,) = _extract(target)

    assert isinstance(unit, AuditableFileUnit)
    assert unit.unit_type == "file"
    assert unit.unit_id == str(target)
    assert unit.get_content() == "x = 1\ny = 2\nz = 3\n"
    assert unit.get_location() == Location(source=str(target), start_line=1, end_line=3)
    assert unit.get_context() == UnitContext()


@pytest.mark.parametrize("language", ["python", None])
def test_whole_file_unit_carries_the_language_in_the_traits_of_the_file(
    tmp_path: Path, language: str | None
) -> None:
    # The name of the file says nothing about its language; only the traits do.
    target = write_text(tmp_path / "notes.txt", "x = 1\n")

    (unit,) = _extract(target, language)

    assert unit.language == language


def test_whole_file_extractor_gives_no_unit_for_a_binary_file(tmp_path: Path) -> None:
    target = tmp_path / "blob.dat"
    target.write_bytes(b"\x00\x01\x02")

    assert _extract(target) == []
