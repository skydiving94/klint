"""Where an audit's input is read from: a disk, a document, a stream or a call."""

from abc import ABC, abstractmethod
from typing import Generic, TypeVar

from klint.core.interfaces.scan_progress_listener import BaseScanProgressListener
from klint.core.models.audit_input import AuditInput

# What a source reads its audit input into, such as a scanned directory tree
# or a parsed document.
InputT_co = TypeVar("InputT_co", covariant=True)


class BaseAuditSource(ABC, Generic[InputT_co]):
    """Reads one audit input into the form its extractor takes."""

    @abstractmethod
    async def read_input(self) -> InputT_co:
        """Return the input, read. Raises when it cannot be read."""

    @abstractmethod
    def count_scanned_files(self) -> int:
        """Return the number of files read so far; none for content in memory."""


class BaseAuditSourceFactory(ABC, Generic[InputT_co]):
    """Makes the source that reads each audit input of a kind of audit."""

    @abstractmethod
    def create_source(
        self,
        audit_input: AuditInput,
        scan_progress_listener: BaseScanProgressListener | None = None,
    ) -> BaseAuditSource[InputT_co]:
        """Return the source that reads ``audit_input``.

        The listener, when given, is told about each directory as it is
        scanned; a source that scans none leaves it alone. Raises ValueError
        when this factory cannot read such an input.
        """
