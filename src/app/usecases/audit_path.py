"""Audit a file or directory path: the run loop shared by every front end."""

import asyncio
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from src.app.audit_mode import AuditMode
from src.app.audit_pipeline import AuditPipeline
from src.core.auditor import Auditor
from src.core.interfaces.scan_progress_listener import BaseScanProgressListener
from src.core.models.report import AuditFinding, AuditReport
from src.core.models.rule import AuditRule
from src.core.models.unit import AuditableUnit

DEFAULT_MAX_CONCURRENT_AUDITS = 8


class AuditListener(Protocol):
    """Told about each target as the audit goes, for progress and errors."""

    def target_failed(self, name: str, error: Exception) -> None: ...

    def target_done(self, name: str) -> None: ...


@dataclass(frozen=True)
class AuditPlan:
    """A validated request: what is reported on, what is audited, and the rules."""

    targets: list[Path]
    units: list[AuditableUnit]
    rules: list[AuditRule]


@dataclass(frozen=True)
class AuditPathResult:
    """The targets audited without error, and the selected findings in unit order."""

    examined: list[str]
    findings: list[AuditFinding]


class AuditPath:
    """Audits every unit found under a path.

    The pipeline prepares what will be audited. Each unit is then audited on
    its own, a limited number of them at a time.
    """

    def __init__(
        self,
        auditor: Auditor,
        audit_pipeline: AuditPipeline,
        audit_mode: AuditMode,
        max_concurrent: int = DEFAULT_MAX_CONCURRENT_AUDITS,
    ) -> None:
        self._auditor = auditor
        self._audit_pipeline = audit_pipeline
        self._audit_mode = audit_mode
        self._max_concurrent = max_concurrent

    async def prepare(
        self,
        target: Path,
        rules_source: Path | None = None,
        scan_progress_listener: BaseScanProgressListener | None = None,
    ) -> AuditPlan:
        """Check the target and the rules; raise if either cannot be used.

        The listener, when given, is told about each directory as it is scanned.
        """
        pending_audit_portfolio = await self._audit_pipeline.prepare_audit(
            target, self._audit_mode, scan_progress_listener
        )
        rules = await self._auditor.load_rules(rules_source)
        return AuditPlan(
            targets=pending_audit_portfolio.targets,
            units=pending_audit_portfolio.units,
            rules=rules,
        )

    async def run(
        self,
        plan: AuditPlan,
        fails_only: bool = True,
        min_confidence: float = 0.0,
        listener: AuditListener | None = None,
    ) -> AuditPathResult:
        target_names = [str(target) for target in plan.targets]
        target_name_set = set(target_names)
        failed: set[str] = set()
        semaphore = asyncio.Semaphore(self._max_concurrent)

        async def audit(unit: AuditableUnit) -> list[AuditFinding]:
            name = unit.unit_id
            async with semaphore:
                try:
                    report = AuditReport()
                    for finding in await self._auditor.audit_unit(unit, plan.rules):
                        report.record(finding)
                    return report.get_findings(fails_only, min_confidence)
                except Exception as error:
                    failed.add(name)
                    if listener is not None:
                        listener.target_failed(name, error)
                    return []
                finally:
                    if listener is not None and name in target_name_set:
                        listener.target_done(name)

        findings = [
            finding
            for unit_findings in await asyncio.gather(
                *(audit(unit) for unit in plan.units)
            )
            for finding in unit_findings
        ]
        examined = [name for name in target_names if name not in failed]
        return AuditPathResult(examined=examined, findings=findings)
