"""Finds a finding by its entry ID in the code as it stands, without a judge."""

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from injector import inject

from klint.app.acknowledgements.finding_identity import (
    FindingIdentity,
    identify_unit_finding,
)
from klint.app.audit_kind_registry import AuditKindRegistry
from klint.app.pipeline.audit_preparer import AuditPreparer
from klint.core.models.audits import DiskPathInput
from klint.core.models.reports import (
    AcknowledgementEntry,
    AcknowledgementStatus,
    FlaggedFinding,
    FlaggedUnit,
)
from klint.core.models.rules import AuditRule
from klint.core.models.units import AuditableUnit, Location

# What a rebuilt entry records as the judge's answer: no judge was asked here.
_UNJUDGED_ANSWER = "not judged"


@dataclass(frozen=True)
class RebuiltFinding:
    """A finding a rule could make on a unit, as the code now stands.

    identity is the finding's identity, rule the rule, and unit_kind and
    location the unit's type and where it sits.
    """

    identity: FindingIdentity
    rule: AuditRule
    unit_kind: str
    location: Location

    def build_acknowledged_entry(
        self, note: str, acknowledged_at: str
    ) -> AcknowledgementEntry:
        """Return the log entry acknowledging this finding, with ``note``.

        No judge flagged it here, so the entry records no confidence and no
        judge model version.
        """
        return AcknowledgementEntry(
            entry_id=self.identity.build_entry_id(),
            rule_id=self.identity.rule_id,
            unit=FlaggedUnit(
                file=self.identity.file,
                kind=self.unit_kind,
                name=self.identity.unit_name,
                start_line=self.location.start_line,
                end_line=self.location.end_line,
            ),
            code_hash=self.identity.code_hash,
            finding=FlaggedFinding(
                answer=_UNJUDGED_ANSWER,
                question=self.rule.find_question(self.unit_kind),
                confidence=None,
            ),
            judge_model_version=None,
            first_flagged_at=acknowledged_at,
            status=AcknowledgementStatus.ACKNOWLEDGED,
            acknowledged_at=acknowledged_at,
            note=note,
        )


class FindingRebuilding:
    """Rebuilds the findings an audit of a repository could make, judging nothing.

    Each unit the audit would go through is paired with each rule it would
    be asked, as an audit of the whole repository chooses them: the
    built-in rules and the project's, less its rule exclusions.
    """

    @inject
    def __init__(
        self, audit_kind_registry: AuditKindRegistry, audit_preparer: AuditPreparer
    ) -> None:
        self._audit_kind_registry = audit_kind_registry
        self._audit_preparer = audit_preparer

    async def find_findings(
        self,
        entry_id: str,
        audit_kind_ids: Sequence[str],
        repository_root: Path,
        working_directory: Path,
    ) -> tuple[RebuiltFinding, ...]:
        """Return each finding of the ``audit_kind_ids`` kinds with the ID ``entry_id``.

        The units' paths are from ``working_directory``, as an audit run
        there names them. Raises when the repository or a rule source cannot
        be read.
        """
        matches: dict[FindingIdentity, RebuiltFinding] = {}
        for kind_id in audit_kind_ids:
            audit_kind = self._audit_kind_registry.find_audit_kind(kind_id)
            portfolio = await self._audit_preparer.prepare_audit(
                DiskPathInput(_relate_to(repository_root, working_directory)),
                audit_kind,
            )
            for unit in portfolio.units:
                for rule in portfolio.rule_set.select_rules_for(unit):
                    finding = _rebuild_finding(
                        rule, unit, repository_root, working_directory
                    )
                    if (
                        finding is not None
                        and finding.identity.build_entry_id() == entry_id
                    ):
                        matches.setdefault(finding.identity, finding)
        return tuple(matches.values())


def _rebuild_finding(
    rule: AuditRule,
    unit: AuditableUnit,
    repository_root: Path,
    working_directory: Path,
) -> RebuiltFinding | None:
    location = unit.get_location()
    if location is None:
        return None
    identity = identify_unit_finding(
        rule.rule_id, unit.unit_id, location, repository_root, working_directory
    )
    if identity is None:
        return None
    return RebuiltFinding(
        identity=identity, rule=rule, unit_kind=unit.unit_type, location=location
    )


def _relate_to(path: Path, working_directory: Path) -> Path:
    """Return ``path`` from ``working_directory`` when it is inside it, else as is."""
    try:
        return path.resolve().relative_to(working_directory.resolve())
    except ValueError:
        return path
