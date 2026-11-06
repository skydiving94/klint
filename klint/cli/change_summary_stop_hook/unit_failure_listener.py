"""Takes note of the units an audit could not audit, such as when the judge is down."""

from klint.core.interfaces import BaseAuditProgressListener


class UnitFailureListener(BaseAuditProgressListener):
    """Records the error each unit's audit failed with, in the order they fail."""

    def __init__(self) -> None:
        self._unit_id_to_error: dict[str, Exception] = {}

    def report_audit_started(self, unit_count: int) -> None:
        del unit_count

    def report_unit_audited(self, unit_id: str) -> None:
        del unit_id

    def report_unit_failed(self, unit_id: str, error: Exception) -> None:
        self._unit_id_to_error[unit_id] = error

    def describe_failures(self, unit_count: int) -> str | None:
        """Say how many of the ``unit_count`` units failed, and why the first did.

        None when none failed.
        """
        if not self._unit_id_to_error:
            return None
        unit_id, error = next(iter(self._unit_id_to_error.items()))
        return (
            f"{len(self._unit_id_to_error)} of the {unit_count} summaries could "
            f"not be checked; {unit_id} because {error}"
        )
