"""Extracts what a file contents audit goes through: the units of each file."""

from injector import inject

from klint.catalog.common.extractors.whole_file import WholeFileExtractor
from klint.core.interfaces.extractor import BaseUnitExtractor
from klint.core.interfaces.target_extractor import BaseTargetExtractor
from klint.core.klint_warning import leave_out_file_on_failure
from klint.core.models.scanned_tree import ScannedFile, ScannedTarget
from klint.core.models.unit import AuditableUnit


class FileContentsExtractor(BaseTargetExtractor):
    """Extracts each file of a target by the extractor that matches its traits.

    A file is read by the extractor registered for the language in its
    traits. A file with nothing registered for its language is read as one
    whole file. A file the extractor fails on gives no unit, and a warning.
    """

    @inject
    def __init__(
        self, language_to_unit_extractor: dict[str, BaseUnitExtractor]
    ) -> None:
        self._language_to_unit_extractor = {
            language.lower(): extractor
            for language, extractor in language_to_unit_extractor.items()
        }
        self._language_neutral_unit_extractor = WholeFileExtractor()

    async def extract_units(self, scanned_target: ScannedTarget) -> list[AuditableUnit]:
        units: list[AuditableUnit] = []
        for scanned_file in scanned_target.files:
            units.extend(await self._extract_file_units(scanned_file))
        return units

    async def _extract_file_units(
        self, scanned_file: ScannedFile
    ) -> list[AuditableUnit]:
        """Return the units of one file; none when the extractor fails on it."""
        extractor: BaseUnitExtractor = self._language_neutral_unit_extractor
        language = scanned_file.traits.language
        if language is not None:
            extractor = self._language_to_unit_extractor.get(
                language.lower(), extractor
            )
        with leave_out_file_on_failure(scanned_file.path):
            return await extractor.extract(scanned_file)
        return []
