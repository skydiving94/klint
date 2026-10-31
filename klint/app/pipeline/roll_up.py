"""The roll-up stage: what the problems on nested units say about their holders."""

from collections.abc import Sequence

from klint.core.models.report import AuditReport
from klint.core.models.roll_up_status import RollUpStatus
from klint.core.models.unit import AuditableUnit
from klint.core.models.unit_tree import (
    list_ancestor_unit_ids,
    map_unit_id_to_parent_unit_id,
)


class FindingRollUp:
    """Records each unit's parent, and each audited unit's roll-up status.

    An audited unit with a problem of its own has OWN_PROBLEM. One with none
    but with a problem on a unit nested in it, at any depth, has
    DESCENDANT_PROBLEM, also when a unit in between was not audited. Any
    other audited unit has NO_PROBLEM.
    """

    def roll_up(
        self,
        report: AuditReport,
        units: Sequence[AuditableUnit],
        min_confidence: float = 0.0,
    ) -> AuditReport:
        """Return ``report`` with the parents in ``units`` and the statuses.

        ``units`` are the units the audit went through; the units nested in
        them count too. A problem counts only with at least
        ``min_confidence``, as for the findings a report selects.
        """
        rolled_up_report = report.copy_with_findings(report.list_findings())
        unit_id_to_parent_unit_id = map_unit_id_to_parent_unit_id(units)
        for unit_id, parent_unit_id in unit_id_to_parent_unit_id.items():
            rolled_up_report.record_unit_parent(unit_id, parent_unit_id)
        own_problem_unit_ids = {
            finding.unit_id
            for finding in report.select_findings(min_confidence=min_confidence)
        }
        descendant_problem_unit_ids = {
            ancestor_unit_id
            for unit_id in own_problem_unit_ids
            for ancestor_unit_id in list_ancestor_unit_ids(
                unit_id, unit_id_to_parent_unit_id
            )
        }
        for unit_id in report.audited_unit_ids():
            if unit_id in own_problem_unit_ids:
                status = RollUpStatus.OWN_PROBLEM
            elif unit_id in descendant_problem_unit_ids:
                status = RollUpStatus.DESCENDANT_PROBLEM
            else:
                status = RollUpStatus.NO_PROBLEM
            rolled_up_report.record_roll_up_status(unit_id, status)
        return rolled_up_report
