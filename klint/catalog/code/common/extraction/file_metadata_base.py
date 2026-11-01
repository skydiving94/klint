from abc import ABC, abstractmethod

from klint.catalog.code.common.units.file_metadata import AuditableFileMetadataUnit
from klint.catalog.domain_neutral.extraction.dispatched_file import DispatchedFile


class BaseFileMetadataExtractor(ABC):
    """Extracts the structural metadata of one file."""

    @abstractmethod
    def extract_file(
        self, dispatched_file: DispatchedFile
    ) -> AuditableFileMetadataUnit:
        """Return the metadata of ``dispatched_file``.

        A binary file is not read: see list_binary_file.
        """


def list_binary_file(dispatched_file: DispatchedFile) -> AuditableFileMetadataUnit:
    """Return the unit of a binary file: its name and path, with no line count.

    Its content is not text, so it is given no language.
    """
    path = dispatched_file.path
    return AuditableFileMetadataUnit(
        unit_id=str(path), file_name=path.name, file_path=str(path), line_count=None
    )
