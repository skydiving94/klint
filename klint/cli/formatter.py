import sys
from collections import defaultdict
from collections.abc import Mapping, Sequence
from pathlib import Path

from klint.core.interfaces.scan_progress_listener import BaseScanProgressListener
from klint.core.models.location import Location
from klint.core.models.report import AuditFinding
from klint.core.models.roll_up_status import RollUpStatus
from klint.core.models.scale import AnswerChoice


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

    def __init__(self, enabled: bool = True) -> None:
        self._total = 1
        self._completed = 0
        self._enabled = enabled and sys.stderr.isatty()

    def start(self, total: int) -> None:
        """Show an empty bar for ``total`` units."""
        self._total = max(total, 1)
        if not self._enabled:
            return
        self._render(f"Initializing model & auditing {self._total} units...")

    def advance(self, unit_id: str) -> None:
        """Count the unit ``unit_id`` as done."""
        if not self._enabled:
            return
        self._completed += 1
        self._render(f"Audited {_find_directory_of(unit_id)}")

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


def _find_directory_of(unit_id: str) -> str:
    """Return the directory a unit is, or sits in; the ID of a unit is its path."""
    path = Path(unit_id)
    return str(path if path.is_dir() else path.parent)


# How an answer that is not a problem is styled, by its sort rank: those that
# sort right after the problems as needing a look, the next as fine, the
# rest as not mattering.
_NON_PROBLEM_SORT_RANK_TO_STYLE = {
    0: _ANSI.BOLD + _ANSI.YELLOW,
    1: _ANSI.BOLD + _ANSI.YELLOW,
    2: _ANSI.BOLD + _ANSI.GREEN,
}


def _pick_answer_style(answer: AnswerChoice) -> str:
    """Return the style of ``answer``, from its scale: a problem is bold red."""
    if answer.is_problem:
        return _ANSI.BOLD + _ANSI.RED
    return _NON_PROBLEM_SORT_RANK_TO_STYLE.get(answer.sort_rank, _ANSI.DIM)


def _format_badge(answer: AnswerChoice) -> str:
    return f"{_pick_answer_style(answer)}[{answer.label.upper()}]{_ANSI.RESET}"


def _format_confidence_bar(
    confidence: float | None, is_problem: bool, width: int = 10
) -> str:
    """Return the bar of ``confidence``; coloured by it for a problem, else dim."""
    if confidence is None:
        return f"{_ANSI.DIM}n/a{_ANSI.RESET}"
    clamped = max(0.0, min(1.0, confidence))
    filled = round(clamped * width)
    bar = "\u2588" * filled + "\u2591" * (width - filled)
    pct = f"{clamped * 100:5.1f}%"
    color = _ANSI.DIM
    if is_problem and clamped >= 0.75:
        color = _ANSI.RED
    elif is_problem and clamped >= 0.4:
        color = _ANSI.YELLOW
    return f"{color}{bar}{_ANSI.RESET} {_ANSI.BOLD}{pct}{_ANSI.RESET}"


_ROLL_UP_STATUS_TO_STYLE = {
    RollUpStatus.OWN_PROBLEM: _ANSI.BOLD + _ANSI.RED,
    RollUpStatus.DESCENDANT_PROBLEM: _ANSI.BOLD + _ANSI.YELLOW,
    RollUpStatus.NO_PROBLEM: _ANSI.GREEN,
}


def _format_roll_up_badge(status: RollUpStatus | None) -> str:
    """Return the badge of a unit's roll-up status; none for a unit with none."""
    if status is None:
        return ""
    label = status.value.replace("_", " ").upper()
    return f" {_ROLL_UP_STATUS_TO_STYLE[status]}[{label}]{_ANSI.RESET}"


def _format_evidence_suffix(evidence_location: Location | None) -> str:
    """Return where a finding's evidence sits, as shown after its rule; may be ""."""
    if evidence_location is None:
        return ""
    line_range = evidence_location.line_range
    lines = "" if line_range is None else f" lines {line_range[0]}-{line_range[1]}"
    return f" {_ANSI.DIM}(evidence: {evidence_location.path}{lines}){_ANSI.RESET}"


def format_audit_report(
    findings: Sequence[AuditFinding],
    scanned_file_count: int,
    audited_unit_count: int,
    no_problems_message: str,
    unit_id_to_roll_up_status: Mapping[str, RollUpStatus] | None = None,
) -> str:
    """Return the terminal report of ``findings``, unit_id_to_findings by unit.

    Each unit shown carries its roll-up status from
    ``unit_id_to_roll_up_status``. A unit with no finding shown is shown too
    when a problem was found on a unit nested in it. With no finding to
    show, the report says ``no_problems_message``.
    """
    unit_id_to_roll_up_status = unit_id_to_roll_up_status or {}
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
            f"{_ANSI.BOLD}{_ANSI.GREEN}\u2714 {no_problems_message}{_ANSI.RESET}\n"
        )
        return "\n".join(lines)

    unit_id_to_findings: dict[str, list[AuditFinding]] = defaultdict(list)
    for finding in findings:
        unit_id_to_findings[finding.unit_id].append(finding)

    fail_count = sum(1 for finding in findings if finding.is_problem())

    # Units in audited order, then any others with findings in theirs.
    shown_unit_ids = dict.fromkeys(
        [
            unit_id
            for unit_id, status in unit_id_to_roll_up_status.items()
            if unit_id in unit_id_to_findings
            or status is RollUpStatus.DESCENDANT_PROBLEM
        ]
        + list(unit_id_to_findings)
    )
    for unit_id in shown_unit_ids:
        lines.append(
            f"\n{_ANSI.BOLD}Target:{_ANSI.RESET} {_ANSI.CYAN}{unit_id}{_ANSI.RESET}"
            f"{_format_roll_up_badge(unit_id_to_roll_up_status.get(unit_id))}"
        )
        if unit_id not in unit_id_to_findings:
            lines.append(
                f"      {_ANSI.DIM}\u21b3 A problem was found in a unit nested in "
                f"it{_ANSI.RESET}"
            )
        for finding in unit_id_to_findings.get(unit_id, []):
            line_range = finding.location.line_range if finding.location else None

            loc_suffix = ""
            if line_range is not None:
                loc_suffix = (
                    f" {_ANSI.DIM}(lines {line_range[0]}-{line_range[1]}){_ANSI.RESET}"
                )
            loc_suffix += _format_evidence_suffix(finding.evidence_location)

            lines.append(
                f"  {_format_badge(finding.answer)} "
                f"{_ANSI.BOLD}{finding.rule_id}{_ANSI.RESET}{loc_suffix}  "
                "Confidence: "
                f"{_format_confidence_bar(finding.confidence, finding.is_problem())}"
            )
            if finding.question:
                lines.append(f"      {_ANSI.DIM}\u21b3 {finding.question}{_ANSI.RESET}")

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
