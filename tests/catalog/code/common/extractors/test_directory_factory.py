"""The directory factory: which unit describes a directory."""

import asyncio
from pathlib import Path

from src.catalog.code.common.extractors.directory_factory import (
    BaseDirectoryUnitFactory,
)
from src.catalog.code.common.extractors.project import RecursiveProjectExtractor
from src.catalog.code.common.units.directory import AuditableDirectoryUnit
from src.catalog.code.common.units.file_metadata import AuditableFileMetadataUnit
from tests.support.builders import write_text


class PlainDirectoryUnit(AuditableDirectoryUnit):
    """A directory described by its name alone."""

    unit_type = "plain_directory"

    def get_content(self) -> str:
        return self.directory_name


class PlainDirectoryFactory(BaseDirectoryUnitFactory):
    def build(
        self,
        directory: Path,
        files: list[AuditableFileMetadataUnit],
        subdirectories: list[AuditableDirectoryUnit],
    ) -> AuditableDirectoryUnit:
        return PlainDirectoryUnit(
            unit_id=str(directory),
            directory_path=str(directory),
            files=files,
            subdirectories=subdirectories,
        )


def test_directory_factory_decides_the_unit_for_every_directory(
    tmp_path: Path,
) -> None:
    write_text(tmp_path / "docs" / "guide" / "intro.md", "# Intro\n")
    extractor = RecursiveProjectExtractor(
        file_extractors=[], directory_factory=PlainDirectoryFactory()
    )

    (root,) = asyncio.run(extractor.extract(tmp_path / "docs"))

    assert isinstance(root, PlainDirectoryUnit)
    assert root.get_content() == "docs"
    (guide,) = root.subdirectories
    assert isinstance(guide, PlainDirectoryUnit)
    assert [f.file_name for f in guide.files] == ["intro.md"]
