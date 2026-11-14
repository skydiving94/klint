"""Prepares an audit: works out what will be audited before any rule is applied."""

from dataclasses import dataclass

from injector import inject

from klint.app.pipeline.acquisition import UnitAcquisition
from klint.app.pipeline.rule_selection import RuleSelection
from klint.core.interfaces import (
    AuditKind,
    BaseRuleSource,
    BaseScanProgressListener,
    BaseUnitSelector,
)
from klint.core.models.audits import AuditInput
from klint.core.models.rules import RuleSet
from klint.core.models.units import AuditableUnit


@dataclass(frozen=True)
class PendingAuditPortfolio:
    """Everything one audit run will go through, prepared and not yet audited.

    units are what the rules will be applied to: the units extracted from
    the input, nested ones included, that the run selects and at least one
    rule applies to. rule_set chooses the rules to ask about each unit.
    scanned_file_count is the number of files read. extracted_unit_count is
    the number of units the input held, before any was left out, and
    selected_unit_count the number the run selected among them.
    """

    units: list[AuditableUnit]
    rule_set: RuleSet
    scanned_file_count: int
    extracted_unit_count: int
    selected_unit_count: int


class AuditPreparer:
    """Prepares an audit of an input: acquires its units, then selects rules.

    A unit selector, when given, chooses the units the run goes on with.
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
        custom_rule_source: BaseRuleSource | None = None,
        scan_progress_listener: BaseScanProgressListener | None = None,
        unit_selector: BaseUnitSelector | None = None,
    ) -> PendingAuditPortfolio:
        """Read ``audit_input``, extract its units and load their rules.

        Raises when the input or a rule source cannot be used. The rules of
        ``custom_rule_source``, when given, merge over the loaded ones. The
        listener, when given, is told about each directory as it is scanned.
        ``unit_selector``, when given, chooses the units among those
        extracted, before their rules are selected.
        """
        acquired_units = await self._unit_acquisition.acquire_units(
            audit_input, audit_kind, scan_progress_listener
        )
        selected_units = (
            acquired_units.units
            if unit_selector is None
            else unit_selector.select_units(acquired_units.units)
        )
        rule_set = await self._rule_selection.select_rules(
            selected_units, audit_kind, custom_rule_source
        )
        return PendingAuditPortfolio(
            units=[unit for unit in selected_units if rule_set.select_rules_for(unit)],
            rule_set=rule_set,
            scanned_file_count=acquired_units.scanned_file_count,
            extracted_unit_count=len(acquired_units.units),
            selected_unit_count=len(selected_units),
        )
