from collections import defaultdict
from typing import Any, Dict, List, Sequence


class _ANSI:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    CYAN = "\033[96m"


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
    bar = "█" * filled + "░" * (width - filled)
    pct = f"{clamped * 100:5.1f}%"
    color = _ANSI.RED if clamped >= 0.75 else (
        _ANSI.YELLOW if clamped >= 0.4 else _ANSI.DIM)
    return f"{color}{bar}{_ANSI.RESET} {_ANSI.BOLD}{pct}{_ANSI.RESET}"


def format_audit_report(
    examined_targets: Sequence[str],
    issues: List[Dict[str, Any]],
    target_label: str = "files",
) -> str:
    lines: List[str] = []
    lines.append(
        f"\n{_ANSI.BOLD}klint Audit Report{_ANSI.RESET} "
        f"{_ANSI.DIM}({len(examined_targets)} {target_label} scanned){_ANSI.RESET}"
    )
    lines.append("─" * 72)

    if not issues:
        lines.append(
            f"{_ANSI.BOLD}{_ANSI.GREEN}✔ No architectural or semantic issues found.{_ANSI.RESET}\n"
        )
        return "\n".join(lines)

    grouped: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for issue in issues:
        unit_id = str(issue.get("unit_id", "unknown"))
        grouped[unit_id].append(issue)

    fail_count = sum(1 for i in issues if str(
        i.get("judgment", "")).upper() == "FAIL")

    for unit_id, unit_issues in grouped.items():
        lines.append(
            f"\n{_ANSI.BOLD}Target:{_ANSI.RESET} {_ANSI.CYAN}{unit_id}{_ANSI.RESET}")
        for issue in unit_issues:
            judgment = str(issue.get("judgment", "UNKNOWN"))
            rule_id = str(issue.get("rule_id", "unknown_rule"))
            confidence = issue.get("confidence")
            instructions = str(issue.get("instructions", ""))
            line_range = issue.get("line_range")

            loc_suffix = ""
            if isinstance(line_range, list) and len(line_range) == 2:
                loc_suffix = f" {_ANSI.DIM}(lines {line_range[0]}-{line_range[1]}){_ANSI.RESET}"

            lines.append(
                f"  {_badge(judgment)} {_ANSI.BOLD}{rule_id}{_ANSI.RESET}{loc_suffix}  "
                f"Confidence: {_confidence_bar(confidence)}"
            )
            if instructions:
                lines.append(f"      {_ANSI.DIM}↳ {instructions}{_ANSI.RESET}")

    lines.append("\n" + "─" * 72)
    summary_color = _ANSI.RED if fail_count > 0 else _ANSI.GREEN
    lines.append(
        f"{_ANSI.BOLD}Summary:{_ANSI.RESET} "
        f"{len(examined_targets)} {target_label} examined | "
        f"{summary_color}{_ANSI.BOLD}{fail_count} failure(s){_ANSI.RESET} | "
        f"{len(issues)} total finding(s) displayed\n"
    )
    return "\n".join(lines)
