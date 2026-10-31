"""Prepares an audit: works out what will be audited before any rule is applied."""

from dataclasses import dataclass
from pathlib import Path

from injector import inject

from klint.app.pipeline.acquisition import UnitAcquisition
from klint.app.pipeline.rule_selection import RuleSelection
from klint.core.interfaces.scan_progress_listener import BaseScanProgressListener
from klint.core.models.audit_input import AuditInput
from klint.core.models.audit_kind import AuditKind
from klint.core.models.rule_set import RuleSet
from klint.core.models.unit import AuditableUnit


@dataclass(frozen=True)
class PendingAuditPortfolio:
    """Everything one audit run will go through, prepared and not yet audited.

    units are what the rules will be applied to: the units extracted from
    the input, nested ones included, that at least one rule applies to.
    rule_set chooses the rules to ask about each unit. scanned_file_count is
    the number of files read.
    """

    units: list[AuditableUnit]
    rule_set: RuleSet
    scanned_file_count: int


class AuditPreparer:
    """Prepares an audit of an input: acquires its units, then selects rules.

    The units that no rule applies to are left out. No rule is applied here
    and no judge is asked.
    """

    @inject
    def __init__(
        self, unit_acquisition: UnitAcquisition, rule_selection: RuleSelection
    ) -> None:
        self._unit_acquisition = unit_acquisition
        self._rule_selection = rule_selection

    async def prepare_audit(
        self,
        audit_input: AuditInput,
        audit_kind: AuditKind,
        *,
        custom_rules_source: Path | None = None,
        scan_progress_listener: BaseScanProgressListener | None = None,
    ) -> PendingAuditPortfolio:
        """Read ``audit_input``, extract its units and load their rules.

        Raises when the input or a rules file cannot be used. The rules in
        ``custom_rules_source``, when given, merge over the loaded ones. The
        listener, when given, is told about each directory as it is scanned.
        """
        acquired_units = await self._unit_acquisition.acquire_units(
            audit_input, audit_kind, scan_progress_listener
        )
        rule_set = await self._rule_selection.select_rules(
            acquired_units.units, audit_kind, custom_rules_source
        )
        return PendingAuditPortfolio(
            units=[
                unit for unit in acquired_units.units if rule_set.select_rules_for(unit)
            ],
            rule_set=rule_set,
            scanned_file_count=acquired_units.scanned_file_count,
        )
