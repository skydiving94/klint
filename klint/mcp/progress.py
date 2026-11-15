"""Progress notifications to the client, as the units are audited."""

import asyncio
from dataclasses import dataclass
from typing import Protocol

from klint.core.interfaces import BaseAuditProgressListener


class BaseProgressReporter(Protocol):
    """What sends a progress notification to the client: the tool call's context."""

    async def report_progress(
        self, progress: float, total: float | None = None, message: str | None = None
    ) -> None: ...


@dataclass(frozen=True)
class UnitFailure:
    """One unit the audit left out, and why."""

    unit_id: str
    error: Exception


class ProgressNotifyingListener(BaseAuditProgressListener):
    """Sends the client a progress notification as each unit's audit ends.

    The client gets them only when it asked for progress; the SDK drops
    them otherwise. The notifications are sent as tasks, since the auditor
    reports synchronously; wait_for_notifications waits for the last ones.
    unit_failures lists the units left out of the audit.
    """

    def __init__(self, progress_reporter: BaseProgressReporter) -> None:
        self._progress_reporter = progress_reporter
        self._unit_count = 0
        self._ended_unit_count = 0
        self._notifications: set[asyncio.Task[None]] = set()
        self.unit_failures: list[UnitFailure] = []

    def report_audit_started(self, unit_count: int) -> None:
        self._unit_count = unit_count
        self._notify(f"Auditing {unit_count} units")

    def report_unit_audited(self, unit_id: str) -> None:
        self._ended_unit_count += 1
        self._notify(f"Audited {unit_id}")

    def report_unit_failed(self, unit_id: str, error: Exception) -> None:
        self._ended_unit_count += 1
        self.unit_failures.append(UnitFailure(unit_id, error))
        self._notify(f"Skipped {unit_id}: {error}")

    async def wait_for_notifications(self) -> None:
        """Wait until every notification sent so far has gone out."""
        if self._notifications:
            await asyncio.gather(*self._notifications)

    def _notify(self, message: str) -> None:
        task = asyncio.get_running_loop().create_task(
            self._progress_reporter.report_progress(
                self._ended_unit_count, self._unit_count or None, message
            )
        )
        self._notifications.add(task)
        task.add_done_callback(self._notifications.discard)
