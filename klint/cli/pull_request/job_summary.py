"""The Markdown a pull request's check shows in its job summary."""

from klint.cli.pull_request.pull_request_report import (
    PullRequestFinding,
    PullRequestReport,
)

NO_CHANGE_LINE = "klint: no change in this pull request that klint audits."
_NO_VALUE = "—"


def format_job_summary(report: PullRequestReport) -> str:
    """Return the summary of ``report``: one line, or a table of its findings."""
    if report.selected_unit_count == 0 and not report.findings:
        return NO_CHANGE_LINE + "\n"
    threshold = f"at a minimum confidence of {report.min_confidence}"
    if not report.findings:
        return (
            f"klint: no problem found in the {report.selected_unit_count} units "
            f"this pull request changes, {threshold}.\n"
        )
    lines = [
        f"### klint: {_count_findings(len(report.findings))} in this pull request, "
        f"{threshold}",
        "",
        "| File | Lines | Rule | Confidence | Acknowledge |",
        "| --- | --- | --- | --- | --- |",
        *(_format_row(finding) for finding in report.findings),
        "",
        "A finding is fixed in the code, or acknowledged as wrong with its "
        "`klint-ack` command, run in a checkout of the pull request's head, "
        "with the entry it stages pushed. A finding with no command, such as a "
        "directory's, is turned off in `klint.json`'s `rule_exclusions`.",
    ]
    return "\n".join(lines) + "\n"


def _count_findings(count: int) -> str:
    return "1 finding" if count == 1 else f"{count} findings"


def _format_row(finding: PullRequestFinding) -> str:
    location = finding.location
    cells = (
        _NO_VALUE if location is None else f"`{location.path}`",
        _describe_lines(finding),
        f"`{finding.finding.get('rule_id')}`",
        _describe_confidence(finding.finding.get("confidence")),
        _describe_command(finding.describe_acknowledge_command()),
    )
    return "| " + " | ".join(cell.replace("|", "\\|") for cell in cells) + " |"


def _describe_lines(finding: PullRequestFinding) -> str:
    location = finding.location
    if location is None or location.start_line is None:
        return _NO_VALUE
    if location.end_line is None or location.end_line == location.start_line:
        return str(location.start_line)
    return f"{location.start_line}-{location.end_line}"


def _describe_confidence(confidence: object) -> str:
    if isinstance(confidence, int | float):
        return f"{confidence:.2f}"
    return _NO_VALUE


def _describe_command(command: str | None) -> str:
    return _NO_VALUE if command is None else f"`{command}`"
