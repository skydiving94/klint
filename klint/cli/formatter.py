import sys
from collections import defaultdict
from collections.abc import Sequence
from pathlib import Path

from klint.core.interfaces.scan_progress_listener import BaseScanProgressListener
from klint.core.models.report import AuditFinding


class _ANSI:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    CYAN = "\033[96m"


class TerminalScanProgressListener(BaseScanProgressListener):
    """Prints each scanned directory on a line of its own on stderr.

    The lines stay on screen. A scan is over too quickly for a line that is
    updated in place to be seen.
    """

    def __init__(self, enabled: bool = True) -> None:
        self._enabled = enabled and sys.stderr.isatty()

    def report_directory_scanned(self, directory: Path) -> None:
        if not self._enabled:
            return
        print(f"{_ANSI.DIM}Scanning {directory}{_ANSI.RESET}", file=sys.stderr)


class AuditProgressReporter:
    """Renders a live one-line progress bar on stderr and clears it on completion.

    The bar counts the units whose audit has ended, and shows the directory
    of the last one. Several units are audited at once, so there is no single
    current directory.
    """

    def __init__(self, total: int, enabled: bool = True) -> None:
        self._total = max(total, 1)
        self._completed = 0
        self._enabled = enabled and sys.stderr.isatty()

    def start(self) -> None:
        if not self._enabled:
            return
        self._render(f"Initializing model & auditing {self._total} units...")

    def advance(self, unit_id: str) -> None:
        """Count the unit ``unit_id`` as done."""
        if not self._enabled:
            return
        self._completed += 1
        self._render(f"Audited {_directory_of(unit_id)}")

    def finish(self) -> None:
        if not self._enabled:
            return
        sys.stderr.write("\r\033[K")
        sys.stderr.flush()

    def _render(self, status_text: str, width: int = 16) -> None:
        ratio = min(1.0, self._completed / self._total)
        filled = round(ratio * width)
        bar = "\u2588" * filled + "\u2591" * (width - filled)
        pct = f"{ratio * 100:3.0f}%"
        short_status = (
            status_text if len(status_text) <= 48 else "..." + status_text[-45:]
        )
        line = (
            f"\r\033[K{_ANSI.CYAN}{bar}{_ANSI.RESET} "
            f"{_ANSI.BOLD}{self._completed}/{self._total}{_ANSI.RESET} ({pct}) "
            f"{_ANSI.DIM}{short_status}{_ANSI.RESET}"
        )
        sys.stderr.write(line)
        sys.stderr.flush()


def _directory_of(unit_id: str) -> str:
    """Return the directory a unit is, or sits in; the ID of a unit is its path."""
    path = Path(unit_id)
    return str(path if path.is_dir() else path.parent)


def _badge(judgment: str) -> str:
    upper = judgment.upper()
    if upper == "FAIL":
        return f"{_ANSI.BOLD}{_ANSI.RED}[FAIL]{_ANSI.RESET}"
    if upper == "PASS":
        return f"{_ANSI.BOLD}{_ANSI.GREEN}[PASS]{_ANSI.RESET}"
    if upper == "LACK OF EVIDENCE":
        return f"{_ANSI.BOLD}{_ANSI.YELLOW}[LACK OF EVIDENCE]{_ANSI.RESET}"
    return f"{_ANSI.DIM}[{upper}]{_ANSI.RESET}"


def _confidence_bar(confidence: float | None, width: int = 10) -> str:
    if confidence is None:
        return f"{_ANSI.DIM}n/a{_ANSI.RESET}"
    clamped = max(0.0, min(1.0, confidence))
    filled = round(clamped * width)
    bar = "\u2588" * filled + "\u2591" * (width - filled)
    pct = f"{clamped * 100:5.1f}%"
    color = (
        _ANSI.RED
        if clamped >= 0.75
        else (_ANSI.YELLOW if clamped >= 0.4 else _ANSI.DIM)
    )
    return f"{color}{bar}{_ANSI.RESET} {_ANSI.BOLD}{pct}{_ANSI.RESET}"


def _sort_key(finding: AuditFinding) -> tuple:
    confidence = finding.confidence if finding.confidence is not None else -1.0
    return (finding.choice.priority, -confidence, finding.rule_id)


def format_audit_report(
    findings: Sequence[AuditFinding],
    scanned_file_count: int,
    audited_unit_count: int,
) -> str:
    divider = "\u2500" * 72
    lines: list[str] = []
    lines.append(
        f"\n{_ANSI.BOLD}klint Audit Report{_ANSI.RESET} "
        f"{_ANSI.DIM}({scanned_file_count} files scanned, "
        f"{audited_unit_count} units audited){_ANSI.RESET}"
    )
    lines.append(divider)

    if not findings:
        lines.append(
            f"{_ANSI.BOLD}{_ANSI.GREEN}\u2714 No architectural or semantic issues "
            f"found.{_ANSI.RESET}\n"
        )
        return "\n".join(lines)

    grouped: dict[str, list[AuditFinding]] = defaultdict(list)
    for finding in findings:
        grouped[finding.unit_id].append(finding)

    fail_count = sum(1 for finding in findings if finding.is_failure())

    for unit_id, unit_findings in grouped.items():
        lines.append(
            f"\n{_ANSI.BOLD}Target:{_ANSI.RESET} {_ANSI.CYAN}{unit_id}{_ANSI.RESET}"
        )
        for finding in sorted(unit_findings, key=_sort_key):
            line_range = finding.location.line_range if finding.location else None

            loc_suffix = ""
            if line_range is not None:
                loc_suffix = (
                    f" {_ANSI.DIM}(lines {line_range[0]}-{line_range[1]}){_ANSI.RESET}"
                )

            lines.append(
                f"  {_badge(finding.choice.label)} "
                f"{_ANSI.BOLD}{finding.rule_id}{_ANSI.RESET}{loc_suffix}  "
                f"Confidence: {_confidence_bar(finding.confidence)}"
            )
            if finding.instructions:
                lines.append(
                    f"      {_ANSI.DIM}\u21b3 {finding.instructions}{_ANSI.RESET}"
                )

    lines.append("\n" + divider)
    summary_color = _ANSI.RED if fail_count > 0 else _ANSI.GREEN
    lines.append(
        f"{_ANSI.BOLD}Summary:{_ANSI.RESET} "
        f"{scanned_file_count} files scanned | "
        f"{audited_unit_count} units audited | "
        f"{summary_color}{_ANSI.BOLD}{fail_count} failure(s){_ANSI.RESET} | "
        f"{len(findings)} total finding(s) displayed\n"
    )
    return "\n".join(lines)
