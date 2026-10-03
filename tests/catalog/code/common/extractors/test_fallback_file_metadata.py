"""File metadata for files in a language without its own extractor."""

from pathlib import Path

from src.catalog.code.common.extractors.fallback_file_metadata import (
    FallbackFileMetadataExtractor,
)
from tests.support.builders import write_text


def test_fallback_metadata_records_only_name_and_line_count(tmp_path: Path) -> None:
    target = write_text(
        tmp_path / "view.tsx", "import React from 'react';\nexport {};\n"
    )

    unit = FallbackFileMetadataExtractor().extract_file(target)

    assert unit.get_content() == "view.tsx (lines=2)"
    assert unit.imports == []
