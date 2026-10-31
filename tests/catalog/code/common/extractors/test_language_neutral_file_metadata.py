"""File metadata for files in a language without its own extractor."""

from pathlib import Path

from klint.catalog.code.common.extractors.language_neutral_file_metadata import (
    LanguageNeutralFileMetadataExtractor,
)
from klint.core.models.unit_traits import UnitTraits
from tests.support.builders import write_text


def test_language_neutral_metadata_records_only_name_and_line_count(
    tmp_path: Path,
) -> None:
    target = write_text(
        tmp_path / "view.tsx", "import React from 'react';\nexport {};\n"
    )

    traits = UnitTraits(language="typescript")

    unit = LanguageNeutralFileMetadataExtractor().extract_file(target, traits)

    assert (unit.file_name, unit.line_count) == ("view.tsx", 2)
    assert unit.imports == []
    assert unit.language == "typescript"
