"""The acquisition stage: what a run goes through, read from its input."""

from klint.core.interfaces.scan_progress_listener import BaseScanProgressListener
from klint.core.models.acquired_units import AcquiredUnits
from klint.core.models.audit_input import AuditInput
from klint.core.models.audit_kind import AuditKind


class UnitAcquisition:
    """Reads an audit input through its kind of audit and extracts its units."""

    async def acquire_units(
        self,
        audit_input: AuditInput,
        audit_kind: AuditKind,
        scan_progress_listener: BaseScanProgressListener | None = None,
    ) -> AcquiredUnits:
        """Return the units of ``audit_input`` for ``audit_kind``.

        Raises ValueError when the kind does not take that form of input, and
        raises when the input cannot be used. The listener, when given, is
        told about each directory as it is scanned.
        """
        if audit_input.input_kind not in audit_kind.accepted_input_kinds:
            accepted_input_kinds = sorted(
                input_kind.value for input_kind in audit_kind.accepted_input_kinds
            )
            raise ValueError(
                f"The '{audit_kind.kind_id}' audit takes {accepted_input_kinds} "
                f"input, not '{audit_input.input_kind.value}'"
            )
        return await audit_kind.unit_source.read_units(
            audit_input, scan_progress_listener
        )
