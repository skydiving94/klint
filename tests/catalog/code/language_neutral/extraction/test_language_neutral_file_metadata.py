"""File metadata for files in a language without its own extractor."""

from pathlib import Path

from klint.catalog.code.language_neutral.extraction.language_neutral_file_metadata import (  # noqa: E501
    LanguageNeutralFileMetadataExtractor,
)
from klint.catalog.domain_neutral.extraction.dispatched_file import DispatchedFile
from klint.core.models.unit_traits import UnitTraits
from tests.support.builders import write_text


def test_language_neutral_metadata_records_only_name_and_line_count(
    tmp_path: Path,
) -> None:
    target = write_text(
        tmp_path / "view.tsx", "import React from 'react';\nexport {};\n"
    )

    traits = UnitTraits(language="typescript")

    unit = LanguageNeutralFileMetadataExtractor().extract_file(
        DispatchedFile(path=target, traits=traits, is_binary=False)
    )

    assert (unit.file_name, unit.line_count) == ("view.tsx", 2)
    assert unit.imports == []
    assert unit.language == "typescript"
