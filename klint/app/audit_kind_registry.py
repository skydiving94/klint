"""The kinds of audit a run can ask for, gathered from every suite."""

from collections.abc import Sequence

from klint.core.models.audit_kind import AuditKind


class AuditKindRegistry:
    """Finds a kind of audit by its ID.

    Raises ValueError when two of the kinds it is given share an ID.
    """

    def __init__(self, audit_kinds: Sequence[AuditKind]) -> None:
        self._kind_id_to_audit_kind: dict[str, AuditKind] = {}
        for audit_kind in audit_kinds:
            if audit_kind.kind_id in self._kind_id_to_audit_kind:
                raise ValueError(
                    f"Audit kind '{audit_kind.kind_id}' is offered by two suites"
                )
            self._kind_id_to_audit_kind[audit_kind.kind_id] = audit_kind

    def find_audit_kind(self, kind_id: str) -> AuditKind:
        """Return the kind ``kind_id`` names.

        Raises ValueError listing the known IDs when no kind has that ID.
        """
        audit_kind = self._kind_id_to_audit_kind.get(kind_id)
        if audit_kind is None:
            raise ValueError(
                f"Unknown audit kind '{kind_id}'; known kinds: "
                f"{sorted(self._kind_id_to_audit_kind)}"
            )
        return audit_kind
