from abc import ABC, abstractmethod


class BaseAuditProgressListener(ABC):
    """Told when an audit starts, and about each unit as its audit ends."""

    @abstractmethod
    def report_audit_started(self, unit_count: int) -> None:
        """Take note that the audit of ``unit_count`` units is starting."""

    @abstractmethod
    def report_unit_audited(self, unit_id: str) -> None:
        """Take note that the unit ``unit_id`` has been audited."""

    @abstractmethod
    def report_unit_failed(self, unit_id: str, error: Exception) -> None:
        """Take note that auditing the unit ``unit_id`` failed with ``error``.

        The unit is left out of the audit; the other units go on.
        """
