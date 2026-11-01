"""Extracts what a file contents audit goes through: the units of each file."""

import asyncio

from klint.catalog.domain_neutral.extraction.dispatched_file import DispatchedFile
from klint.catalog.domain_neutral.extraction.traits_based_extraction_delegator import (
    TraitsBasedExtractionDelegator,
)
from klint.core.interfaces.extractor import BaseUnitExtractor
from klint.core.klint_warning import leave_out_file_on_failure
from klint.core.models.scanned_tree import ScannedFile, ScannedTarget
from klint.core.models.unit import AuditableUnit


class FileContentsExtractor(BaseUnitExtractor[ScannedTarget]):
    """Extracts each file of a target by the extractor its traits pick.

    A file the extractor fails on gives no unit, and a warning.
    """

    def __init__(
        self,
        delegator: TraitsBasedExtractionDelegator[BaseUnitExtractor[DispatchedFile]],
    ) -> None:
        self._delegator = delegator

    async def extract(self, audit_input: ScannedTarget) -> list[AuditableUnit]:
        units: list[AuditableUnit] = []
        for scanned_file in audit_input.files:
            units.extend(await self._extract_file_units(scanned_file))
        return units

    async def _extract_file_units(
        self, scanned_file: ScannedFile
    ) -> list[AuditableUnit]:
        """Return the units of one file; none when it cannot be extracted."""
        with leave_out_file_on_failure(scanned_file.path):
            dispatch = await asyncio.to_thread(
                self._delegator.dispatch_file, scanned_file
            )
            return await dispatch.extractor.extract(dispatch.dispatched_file)
        return []
