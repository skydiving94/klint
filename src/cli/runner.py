"""What the klint commands share: run the audit, show progress, print the result."""

import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from src.app.usecases.audit_path import AuditPath
from src.cli.formatter import AuditProgressReporter, format_audit_report


@dataclass(frozen=True)
class CommandStyle:
    """How one command names itself and its targets in its output."""

    name: str
    target_label: str
    json_key: str


class _ProgressListener:
    """Advances the progress bar and reports skipped targets on stderr."""

    def __init__(self, progress: AuditProgressReporter, command_name: str) -> None:
        self._progress = progress
        self._command_name = command_name

    def target_failed(self, name: str, error: Exception) -> None:
        self._progress.finish()
        print(f"[{self._command_name}] Skipping {name}: {error}", file=sys.stderr)

    def target_done(self, name: str) -> None:
        self._progress.advance(name)


async def run_audit_command(
    audit_path: AuditPath,
    style: CommandStyle,
    target: Path,
    rules_source: Optional[Path],
    show_all: bool,
    min_confidence: float,
    as_json: bool,
) -> int:
    try:
        plan = await audit_path.prepare(target, rules_source)
    except (FileNotFoundError, ValueError, json.JSONDecodeError) as exc:
        print(f"[{style.name}] Error: {exc}", file=sys.stderr)
        return 1

    progress = AuditProgressReporter(
        total=len(plan.targets), label=style.target_label, enabled=not as_json
    )
    progress.start()
    result = await audit_path.run(
        plan,
        fails_only=not show_all,
        min_confidence=min_confidence,
        listener=_ProgressListener(progress, style.name),
    )
    progress.finish()

    if as_json:
        issues = [finding.to_dict() for finding in result.findings]
        print(json.dumps({style.json_key: result.examined, "issues": issues}, indent=2))
    else:
        print(
            format_audit_report(
                result.examined, result.findings, target_label=style.target_label
            )
        )
    return 0
