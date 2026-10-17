import asyncio

from src.catalog.code.common.extractors.traits_based_extraction_delegator import (
    TraitsBasedExtractionDelegator,
)
from src.catalog.code.common.units.directory import AuditableDirectoryUnit
from src.catalog.code.common.units.file_metadata import AuditableFileMetadataUnit
from src.core.klint_warning import leave_out_file_on_failure
from src.core.models.scanned_tree import ScannedDirectory


class RecursiveProjectExtractor:
    """Builds one composite directory unit for a scanned tree.

    The unit holds the metadata of the files directly in the scanned
    directory and, recursively, of every subdirectory. This class only goes
    through the tree; the delegator decides what reads each file and what
    describes each directory. A file that cannot be read or processed is left
    out, with a warning.
    """

    def __init__(self, delegator: TraitsBasedExtractionDelegator) -> None:
        self._delegator = delegator

    async def extract(
        self, scanned_directory: ScannedDirectory
    ) -> AuditableDirectoryUnit:
        """Return the unit of ``scanned_directory``, holding everything beneath it."""
        return await asyncio.to_thread(self._extract_tree, scanned_directory)

    def _extract_tree(
        self, scanned_directory: ScannedDirectory
    ) -> AuditableDirectoryUnit:
        return self._delegator.update_units_after_full_walk(
            self._build_directory_unit(scanned_directory)
        )

    def _build_directory_unit(
        self, scanned_directory: ScannedDirectory
    ) -> AuditableDirectoryUnit:
        files: list[AuditableFileMetadataUnit] = []
        for scanned_file in scanned_directory.files:
            with leave_out_file_on_failure(scanned_file.path):
                files.append(self._delegator.delegate_file_extraction(scanned_file))
        subdirectories = [
            self._build_directory_unit(scanned_subdirectory)
            for scanned_subdirectory in scanned_directory.subdirectories
        ]
        return self._delegator.delegate_directory_building(
            scanned_directory.path, files, subdirectories
        )
