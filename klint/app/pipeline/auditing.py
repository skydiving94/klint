"""The auditing stage: the judge's answers on each prepared unit."""

from injector import inject

from klint.app.pipeline.audit_preparer import PendingAuditPortfolio
from klint.core.auditor import Auditor
from klint.core.interfaces.audit_progress_listener import BaseAuditProgressListener
from klint.core.models.audit_kind import AuditKind
from klint.core.models.report import AuditReport


class UnitAuditing:
    """Audits the units of a prepared run with the rules selected for them."""

    @inject
    def __init__(self, auditor: Auditor) -> None:
        self._auditor = auditor

    async def audit_units(
        self,
        portfolio: PendingAuditPortfolio,
        audit_kind: AuditKind,
        audit_progress_listener: BaseAuditProgressListener | None = None,
    ) -> AuditReport:
        """Audit every unit of ``portfolio`` for ``audit_kind``; return the report.

        The judge answers on the kind's scale. A unit whose audit fails is
        left out of the report and the others go on. The listener, when
        given, is told when the audit starts and about each unit as its audit
        ends.
        """
        return await self._auditor.audit(
            portfolio.units,
            portfolio.rule_set,
            audit_kind.answer_scale,
            audit_progress_listener,
        )
