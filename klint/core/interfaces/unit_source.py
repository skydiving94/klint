from abc import ABC, abstractmethod

from klint.core.interfaces.scan_progress_listener import BaseScanProgressListener
from klint.core.models.acquired_units import AcquiredUnits
from klint.core.models.audit_input import AuditInput


class BaseUnitSource(ABC):
    """Gives the units of an audit input, whatever form it is read into."""

    @abstractmethod
    async def read_units(
        self,
        audit_input: AuditInput,
        scan_progress_listener: BaseScanProgressListener | None = None,
    ) -> AcquiredUnits:
        """Return the units of ``audit_input``.

        Raises when the input cannot be read or its units extracted. The
        listener, when given, is told about each directory as it is scanned.
        """
