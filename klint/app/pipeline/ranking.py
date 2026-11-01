"""The ranking stage: the order a report lists its findings in."""

from klint.core.models.audit_kind import AuditKind
from klint.core.models.report import AuditFinding, AuditReport


class FindingRanking:
    """Puts the findings of a report in the order a report lists them.

    The findings on one unit stay together, the units in the order their
    findings were recorded. On a unit, the findings come by the sort rank
    of their answer, then by the best rank among their tags in the kind's
    ranked tags, then highest confidence first, then by rule ID. A finding
    with no ranked tag comes after those with one, and a finding with no
    confidence after those with one.
    """

    def rank_findings(self, report: AuditReport, audit_kind: AuditKind) -> AuditReport:
        """Return ``report`` with its findings in report order, for ``audit_kind``."""
        findings = report.list_findings()
        unit_id_to_rank = {
            unit_id: rank
            for rank, unit_id in enumerate(
                dict.fromkeys(finding.unit_id for finding in findings)
            )
        }
        tag_to_rank = {tag: rank for rank, tag in enumerate(audit_kind.ranked_tags)}

        def find_tag_rank(finding: AuditFinding) -> int:
            return min(
                (tag_to_rank[tag] for tag in finding.tags if tag in tag_to_rank),
                default=len(tag_to_rank),
            )

        return report.copy_with_findings(
            sorted(
                findings,
                key=lambda finding: (
                    unit_id_to_rank[finding.unit_id],
                    finding.answer.sort_rank,
                    find_tag_rank(finding),
                    -(finding.confidence if finding.confidence is not None else -1.0),
                    finding.rule_id,
                ),
            )
        )
