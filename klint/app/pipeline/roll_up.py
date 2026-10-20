"""The roll-up stage: what the findings on a unit's children say about it."""

from klint.core.models.report import AuditReport


class FindingRollUp:
    """Carries the findings of nested units up to the units that hold them."""

    def roll_up(self, report: AuditReport) -> AuditReport:
        """Return ``report`` with its findings rolled up.

        No kind of audit rolls findings up yet, so the report is returned as
        it is.
        """
        return report
