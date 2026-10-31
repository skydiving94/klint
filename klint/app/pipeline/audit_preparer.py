"""Prepares an audit: works out what will be audited before any rule is applied."""

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from injector import inject

from klint.app.pipeline.acquisition import UnitAcquisition
from klint.app.pipeline.rule_selection import RuleSelection
from klint.core.interfaces.scan_progress_listener import BaseScanProgressListener
from klint.core.models.audit_input import AuditInput
from klint.core.models.audit_kind import AuditKind
from klint.core.models.rule import AuditRule
from klint.core.models.unit import AuditableUnit


@dataclass(frozen=True)
class PendingAuditPortfolio:
    """Everything one audit run will go through, prepared and not yet audited.

    units are what the rules will be applied to: the units extracted from
    the input, nested ones included, that at least one rule applies to.
    language_to_rules holds, for each language a unit is written in, the
    rules to ask about it; the key None is for units whose language is not
    identified. scanned_file_count is the number of files read.
    """

    units: list[AuditableUnit]
    language_to_rules: dict[str | None, list[AuditRule]]
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
        language_to_rules = await self._rule_selection.select_rules(
            acquired_units.units, audit_kind, custom_rules_source
        )
        return PendingAuditPortfolio(
            units=[
                unit
                for unit in acquired_units.units
                if _is_asked_any_rule(unit, language_to_rules)
            ],
            language_to_rules=language_to_rules,
            scanned_file_count=acquired_units.scanned_file_count,
        )


def _is_asked_any_rule(
    unit: AuditableUnit, language_to_rules: Mapping[str | None, list[AuditRule]]
) -> bool:
    """Return True when a rule loaded for the unit's language applies to it."""
    return any(
        rule.is_applicable_to(unit) for rule in language_to_rules.get(unit.language, [])
    )
