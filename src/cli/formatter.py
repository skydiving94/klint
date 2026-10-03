import sys
from collections import defaultdict
from typing import Dict, List, Sequence

from src.core.models.report import AuditFinding


class _ANSI:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    CYAN = "\033[96m"


class AuditProgressReporter:
    """Renders a live single-line progress bar to stderr and clears it upon completion."""

    def __init__(
        self, total: int, label: str = "files", enabled: bool = True
    ) -> None:
        self._total = max(total, 1)
        self._completed = 0
        self._label = label
        self._enabled = enabled and sys.stderr.isatty()

    def start(self) -> None:
        if not self._enabled:
            return
        self._render(
            f"Initializing model & extracting {self._total} {self._label}...")

    def advance(self, target_name: str) -> None:
        if not self._enabled:
            return
        self._completed += 1
        self._render(f"Audited {target_name}")

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
            status_text if len(status_text) <= 48 else "..." +
            status_text[-45:]
        )
        line = (
            f"\r\033[K{_ANSI.CYAN}{bar}{_ANSI.RESET} "
            f"{_ANSI.BOLD}{self._completed}/{self._total}{_ANSI.RESET} ({pct}) "
            f"{_ANSI.DIM}{short_status}{_ANSI.RESET}"
        )
        sys.stderr.write(line)
        sys.stderr.flush()


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
    examined_targets: Sequence[str],
    findings: Sequence[AuditFinding],
    target_label: str = "files",
) -> str:
    divider = "\u2500" * 72
    lines: List[str] = []
    lines.append(
        f"\n{_ANSI.BOLD}klint Audit Report{_ANSI.RESET} "
        f"{_ANSI.DIM}({len(examined_targets)} {target_label} scanned){_ANSI.RESET}"
    )
    lines.append(divider)

    if not findings:
        lines.append(
            f"{_ANSI.BOLD}{_ANSI.GREEN}\u2714 No architectural or semantic issues found.{_ANSI.RESET}\n"
        )
        return "\n".join(lines)

    grouped: Dict[str, List[AuditFinding]] = defaultdict(list)
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
                f"  {_badge(finding.choice.label)} {_ANSI.BOLD}{finding.rule_id}{_ANSI.RESET}{loc_suffix}  "
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
        f"{len(examined_targets)} {target_label} examined | "
        f"{summary_color}{_ANSI.BOLD}{fail_count} failure(s){_ANSI.RESET} | "
        f"{len(findings)} total finding(s) displayed\n"
    )
    return "\n".join(lines)
