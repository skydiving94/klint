"""Audit a file or directory path: the run loop shared by every front end."""

import asyncio
from collections.abc import Awaitable, Callable, Sequence
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
    """A validated request: where to start, what will be audited, and the rules."""

    root: Path
    targets: list[Path]
    rules: list[AuditRule]


@dataclass(frozen=True)
class AuditPathResult:
    """The targets audited without error, and the selected findings in target order."""

    examined: list[str]
    findings: list[AuditFinding]


class AuditPath:
    """Audits every target found under a path.

    The pipeline lists what will be audited. For a project structure audit,
    the path is extracted once and every unit in the resulting tree is
    audited; for a file contents audit, each target is extracted on its own.
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
            root=target, targets=pending_audit_portfolio.targets, rules=rules
        )

    async def run(
        self,
        plan: AuditPlan,
        fails_only: bool = True,
        min_confidence: float = 0.0,
        listener: AuditListener | None = None,
    ) -> AuditPathResult:
        target_names = [str(target) for target in plan.targets]
        failed: set[str] = set()
        semaphore = asyncio.Semaphore(self._max_concurrent)

        async def audit(
            name: str,
            get_units: Callable[[], Awaitable[Sequence[AuditableUnit]]],
            is_target: bool,
        ) -> list[AuditFinding]:
            async with semaphore:
                try:
                    report = AuditReport()
                    for unit in await get_units():
                        findings = await self._auditor.audit_unit(unit, plan.rules)
                        for finding in findings:
                            report.record(finding)
                    return report.get_findings(fails_only, min_confidence)
                except Exception as error:
                    failed.add(name)
                    if listener is not None:
                        listener.target_failed(name, error)
                    return []
                finally:
                    if listener is not None and is_target:
                        listener.target_done(name)

        if self._audit_mode is AuditMode.PROJECT_STRUCTURE:
            jobs = await self._tree_jobs(
                plan, set(target_names), failed, listener, audit
            )
        else:
            jobs = [
                audit(str(target), self._extract_one(target), True)
                for target in plan.targets
            ]

        findings = [
            finding
            for job_findings in await asyncio.gather(*jobs)
            for finding in job_findings
        ]
        examined = [name for name in target_names if name not in failed]
        return AuditPathResult(examined=examined, findings=findings)

    def _extract_one(
        self, target: Path
    ) -> Callable[[], Awaitable[Sequence[AuditableUnit]]]:
        async def extract() -> Sequence[AuditableUnit]:
            return await self._auditor.extract_units(target)

        return extract

    async def _tree_jobs(
        self,
        plan: AuditPlan,
        target_names: set[str],
        failed: set[str],
        listener: AuditListener | None,
        audit: Callable[
            [str, Callable[[], Awaitable[Sequence[AuditableUnit]]], bool],
            Awaitable[list[AuditFinding]],
        ],
    ) -> list[Awaitable[list[AuditFinding]]]:
        """Extract the whole tree once and return one audit job per unit in it."""
        try:
            units = await self._auditor.extract_units(plan.root, walk_children=True)
        except Exception as error:
            failed.update(target_names)
            if listener is not None:
                listener.target_failed(str(plan.root), error)
                for target in plan.targets:
                    listener.target_done(str(target))
            return []

        def only(
            unit: AuditableUnit,
        ) -> Callable[[], Awaitable[Sequence[AuditableUnit]]]:
            async def get() -> Sequence[AuditableUnit]:
                return [unit]

            return get

        return [
            audit(unit.unit_id, only(unit), unit.unit_id in target_names)
            for unit in units
        ]
