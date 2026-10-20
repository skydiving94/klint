"""Prepares an audit: works out what will be audited before any rule is applied."""

import asyncio
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from injector import inject

from klint.app.audit_kind_registry import AuditKindRegistry
from klint.app.audit_mode import AuditMode
from klint.catalog.code import FILE_CONTENTS_KIND_ID, PROJECT_STRUCTURE_KIND_ID
from klint.catalog.common.scanners.target_scanner import TargetScanner
from klint.core.interfaces.rule_loader import BaseRuleLoader
from klint.core.interfaces.scan_progress_listener import BaseScanProgressListener
from klint.core.models.file_traits import FileTraits
from klint.core.models.rule import AuditRule
from klint.core.models.unit import AuditableUnit

# The kind of audit each mode asks for.
_AUDIT_MODE_TO_KIND_ID = {
    AuditMode.FILE_CONTENTS: FILE_CONTENTS_KIND_ID,
    AuditMode.PROJECT_STRUCTURE: PROJECT_STRUCTURE_KIND_ID,
}


@dataclass(frozen=True)
class PendingAuditPortfolio:
    """Everything one audit run will go through, prepared and not yet audited.

    units are what the rules will be applied to: the units extracted from
    the target, nested ones included, that at least one rule applies to.
    language_to_rules holds, for each language a unit is written in, the
    rules to ask about it; the key None is for units whose language is not
    identified. scanned_file_count is the number of files the scan recorded.
    """

    units: list[AuditableUnit]
    language_to_rules: dict[str | None, list[AuditRule]]
    scanned_file_count: int


class AuditPreparer:
    """Prepares an audit of a target, in fixed steps.

    The target is scanned once. The kind of audit then extracts its units
    from what the scan found. Last, the kind's rules are loaded by the
    traits of the units, and the units that no rule applies to are left out.
    No rule is applied here and no judge is asked.
    """

    @inject
    def __init__(
        self, target_scanner: TargetScanner, audit_kind_registry: AuditKindRegistry
    ) -> None:
        self._target_scanner = target_scanner
        self._audit_kind_registry = audit_kind_registry

    async def prepare_audit(
        self,
        target: Path,
        audit_mode: AuditMode,
        *,
        custom_rules_source: Path | None = None,
        scan_progress_listener: BaseScanProgressListener | None = None,
    ) -> PendingAuditPortfolio:
        """Scan ``target``, extract its units and load their rules.

        Raises when the target or a rules file cannot be used. The rules in
        ``custom_rules_source``, when given, merge over the loaded ones. The
        listener, when given, is told about each directory as it is scanned.
        """
        audit_kind = self._audit_kind_registry.find_audit_kind(
            _AUDIT_MODE_TO_KIND_ID[audit_mode]
        )
        scanned_target = await asyncio.to_thread(
            self._target_scanner.scan_target, target, scan_progress_listener
        )
        units = await audit_kind.extractor.extract_units(scanned_target)
        language_to_rules = await self._load_language_to_rules(
            units, audit_kind.rule_loader, custom_rules_source
        )
        return PendingAuditPortfolio(
            units=[
                unit for unit in units if _is_asked_any_rule(unit, language_to_rules)
            ],
            language_to_rules=language_to_rules,
            scanned_file_count=len(scanned_target.files),
        )

    async def _load_language_to_rules(
        self,
        units: list[AuditableUnit],
        rule_loader: BaseRuleLoader,
        custom_rules_source: Path | None,
    ) -> dict[str | None, list[AuditRule]]:
        """Load the rules for each language the units are written in.

        With no unit, the rules are still loaded once, so that a rules file
        that cannot be used stops the audit whatever the target holds.
        """
        languages = list(dict.fromkeys(unit.language for unit in units)) or [None]
        return {
            language: await rule_loader.load_rules(
                FileTraits(language=language), custom_rules_source
            )
            for language in languages
        }


def _is_asked_any_rule(
    unit: AuditableUnit, language_to_rules: Mapping[str | None, list[AuditRule]]
) -> bool:
    """Return True when a rule loaded for the unit's language applies to it."""
    return any(
        rule.is_applicable_to(unit) for rule in language_to_rules.get(unit.language, [])
    )
