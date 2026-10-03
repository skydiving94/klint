"""Whole-file extraction: one unit per file."""

import asyncio
from pathlib import Path

from src.catalog.common.extractors.whole_file import WholeFileExtractor
from src.catalog.common.units.file import AuditableFileUnit
from tests.support.builders import write_text


def test_whole_file_extractor_returns_one_unit_spanning_the_file(
    tmp_path: Path,
) -> None:
    target = write_text(tmp_path / "a.py", "x = 1\ny = 2\nz = 3\n")

    (unit,) = asyncio.run(WholeFileExtractor().extract(target))

    assert isinstance(unit, AuditableFileUnit)
    assert unit.unit_type == "file"
    assert unit.unit_id == str(target)
    assert unit.get_content() == "x = 1\ny = 2\nz = 3\n"
    assert unit.get_metadata() == {"file_path": str(target), "line_range": [1, 3]}
