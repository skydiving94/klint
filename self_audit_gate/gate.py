import argparse
import json
import os
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from enum import IntEnum
from pathlib import Path

from self_audit_gate.rebuttal_list import (
    Audit,
    FindingKey,
    GateInputError,
    ListedRebuttal,
    read_rebuttal_list,
)

_REBUTTAL_LIST_PATH = ".github/self-audit-rebuttals.json"


class GateExitCode(IntEnum):
    """How the gate ends: every finding rebutted, one open, or unusable input."""

    PASSED = 0
    OPEN_FINDINGS = 1
    INPUT_ERROR = 2


@dataclass(frozen=True)
class AuditFinding:
    """One failure an audit reported."""

    key: FindingKey
    confidence: float | None


@dataclass(frozen=True)
class AuditReport:
    """The audit a JSON report came from, and where it is."""

    audit: Audit
    path: Path


@dataclass(frozen=True)
class GateOutcome:
    """The findings, each with its rebuttal link or None when it is open."""

    finding_to_rebuttal_link: dict[AuditFinding, str | None]
    unmatched_rebuttals: tuple[ListedRebuttal, ...]

    def count_open_findings(self) -> int:
        return sum(link is None for link in self.finding_to_rebuttal_link.values())


def read_audit_findings(report: AuditReport) -> tuple[AuditFinding, ...]:
    """Read the failures in a klint ``--json`` report.

    Raises GateInputError when the file is not such a report.
    """
    try:
        document = json.loads(report.path.read_text(encoding="utf-8"))
        return tuple(
            AuditFinding(
                key=FindingKey(
                    audit=report.audit,
                    rule_id=str(finding["rule_id"]),
                    unit_id=str(finding["unit_id"]),
                ),
                confidence=finding.get("confidence"),
            )
            for finding in document["findings"]
        )
    except (OSError, json.JSONDecodeError, KeyError, TypeError) as error:
        raise GateInputError(
            f"cannot read the {report.audit.value} report {report.path}: {error!r}"
        ) from None


def judge_findings(
    findings: Sequence[AuditFinding], rebuttals: Sequence[ListedRebuttal]
) -> GateOutcome:
    """Match each finding to its listed rebuttal, if it has one."""
    key_to_link = {rebuttal.key: rebuttal.rebuttal_link for rebuttal in rebuttals}
    found_keys = {finding.key for finding in findings}
    return GateOutcome(
        finding_to_rebuttal_link={
            finding: key_to_link.get(finding.key) for finding in findings
        },
        unmatched_rebuttals=tuple(
            rebuttal for rebuttal in rebuttals if rebuttal.key not in found_keys
        ),
    )


def describe_outcome(outcome: GateOutcome) -> str:
    """Write the outcome as Markdown for the job summary."""
    lines = ["### Self-Audit gate", ""]
    if outcome.finding_to_rebuttal_link:
        lines += [
            "| Audit | Rule | Unit | Confidence | Status |",
            "| --- | --- | --- | ---: | --- |",
        ]
        for finding, link in outcome.finding_to_rebuttal_link.items():
            confidence = (
                "" if finding.confidence is None else f"{finding.confidence:.0%}"
            )
            status = "**Open**" if link is None else f"Rebutted ([comment]({link}))"
            key = finding.key
            lines.append(
                f"| {key.audit.value} | `{key.rule_id}` | `{key.unit_id}` "
                f"| {confidence} | {status} |"
            )
        lines.append("")
    open_count = outcome.count_open_findings()
    if open_count:
        lines.append(
            f"**{open_count} open finding(s).** Fix each one, or rebut it in a "
            f"comment on the pull request and list it in `{_REBUTTAL_LIST_PATH}`."
        )
    else:
        lines.append("Every finding is fixed or rebutted.")
    for rebuttal in outcome.unmatched_rebuttals:
        key = rebuttal.key
        lines.append(
            f"- Listed but not found in this run: {key.audit.value} `{key.rule_id}` "
            f"on `{key.unit_id}`. Remove it from the list once it is fixed."
        )
    return "\n".join(lines) + "\n"


def run_gate(argv: Sequence[str] | None = None) -> GateExitCode:
    """Read the reports and the rebuttal list, print the outcome, and end."""
    parser = argparse.ArgumentParser(
        prog="python -m self_audit_gate",
        description=(
            "Fails when a Self-Audit finding is neither fixed nor listed as rebutted."
        ),
    )
    for audit in Audit:
        parser.add_argument(
            f"--{audit.value}", type=Path, help=f"The {audit.value} audit's JSON report"
        )
    parser.add_argument("--rebuttals", type=Path, default=Path(_REBUTTAL_LIST_PATH))
    arguments = parser.parse_args(argv)
    reports = [
        AuditReport(audit=audit, path=getattr(arguments, audit.value))
        for audit in Audit
        if getattr(arguments, audit.value) is not None
    ]
    try:
        if not reports:
            raise GateInputError("give at least one report, --structure or --file")
        findings = [
            finding for report in reports for finding in read_audit_findings(report)
        ]
        outcome = judge_findings(findings, read_rebuttal_list(arguments.rebuttals))
    except GateInputError as error:
        print(f"Self-Audit gate: {error}", file=sys.stderr)
        return GateExitCode.INPUT_ERROR
    description = describe_outcome(outcome)
    print(description)
    summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary_path:
        with Path(summary_path).open("a", encoding="utf-8") as summary:
            summary.write(description)
    if outcome.count_open_findings():
        return GateExitCode.OPEN_FINDINGS
    return GateExitCode.PASSED
