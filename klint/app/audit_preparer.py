"""Prepares an audit: works out what will be audited before any rule is applied."""

import asyncio
from collections.abc import Iterator, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import assert_never

from injector import inject

from klint.app.audit_mode import AuditMode
from klint.catalog.code.common.extractors.project import RecursiveProjectExtractor
from klint.catalog.common.scanners.target_scanner import TargetScanner
from klint.core.interfaces.extractor import BaseUnitExtractor
from klint.core.interfaces.rule_loader import BaseRuleLoader
from klint.core.interfaces.scan_progress_listener import BaseScanProgressListener
from klint.core.klint_warning import leave_out_file_on_failure
from klint.core.models.file_traits import FileTraits
from klint.core.models.rule import AuditRule
from klint.core.models.scanned_tree import ScannedDirectory, ScannedFile
from klint.core.models.unit import AuditableUnit


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

    The target is scanned once. The units are then extracted from what the
    scan found, each file by the extractor that matches its traits. Last, the
    rules are loaded by the same traits, and the units that no rule applies
    to are left out. No rule is applied here and no judge is asked.
    """

    @inject
    def __init__(
        self,
        target_scanner: TargetScanner,
        language_to_unit_extractor: dict[str, BaseUnitExtractor],
        language_neutral_unit_extractor: BaseUnitExtractor,
        project_extractor: RecursiveProjectExtractor,
        audit_mode_to_rule_loader: dict[AuditMode, BaseRuleLoader],
    ) -> None:
        self._target_scanner = target_scanner
        self._language_to_unit_extractor = {
            language.lower(): extractor
            for language, extractor in language_to_unit_extractor.items()
        }
        self._language_neutral_unit_extractor = language_neutral_unit_extractor
        self._project_extractor = project_extractor
        self._audit_mode_to_rule_loader = dict(audit_mode_to_rule_loader)

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
        match audit_mode:
            case AuditMode.FILE_CONTENTS:
                scanned_files, units = await self._extract_file_contents(
                    target, scan_progress_listener
                )
            case AuditMode.PROJECT_STRUCTURE:
                scanned_files, units = await self._extract_project_structure(
                    target, scan_progress_listener
                )
            case _:
                assert_never(audit_mode)
        language_to_rules = await self._load_language_to_rules(
            units, self._audit_mode_to_rule_loader[audit_mode], custom_rules_source
        )
        return PendingAuditPortfolio(
            units=[
                unit for unit in units if _is_asked_any_rule(unit, language_to_rules)
            ],
            language_to_rules=language_to_rules,
            scanned_file_count=len(scanned_files),
        )

    async def _extract_file_contents(
        self, target: Path, scan_progress_listener: BaseScanProgressListener | None
    ) -> tuple[list[ScannedFile], list[AuditableUnit]]:
        """Return the files the scan recorded, and the units of each."""
        scanned_files = await asyncio.to_thread(
            self._scan_files, target, scan_progress_listener
        )
        units: list[AuditableUnit] = []
        for scanned_file in scanned_files:
            units.extend(await self._extract_file_units(scanned_file))
        return scanned_files, units

    def _scan_files(
        self, target: Path, scan_progress_listener: BaseScanProgressListener | None
    ) -> list[ScannedFile]:
        if not target.exists():
            raise FileNotFoundError(f"Audit target does not exist: {target}")
        if target.is_file():
            return [self._target_scanner.scan_file(target)]
        if not target.is_dir():
            # Neither a file nor a directory, such as a named pipe: it holds
            # no file to audit.
            return []
        scanned_target = self._target_scanner.scan_directory(
            target, scan_progress_listener
        )
        return list(scanned_target.yield_files())

    async def _extract_file_units(
        self, scanned_file: ScannedFile
    ) -> list[AuditableUnit]:
        """Return the units of one file, from the extractor that matches its traits.

        A file the extractor fails on gives no unit, and a warning.
        """
        extractor = self._language_neutral_unit_extractor
        language = scanned_file.traits.language
        if language is not None:
            extractor = self._language_to_unit_extractor.get(
                language.lower(), extractor
            )
        with leave_out_file_on_failure(scanned_file.path):
            return await extractor.extract(scanned_file)
        return []

    async def _extract_project_structure(
        self, target: Path, scan_progress_listener: BaseScanProgressListener | None
    ) -> tuple[list[ScannedFile], list[AuditableUnit]]:
        """Return the files the scan recorded, and the units of the tree."""
        scanned_target = await asyncio.to_thread(
            self._scan_project, target, scan_progress_listener
        )
        root_unit = await self._project_extractor.extract(scanned_target)
        return (
            list(scanned_target.yield_files()),
            list(_yield_unit_and_nested_units(root_unit)),
        )

    def _scan_project(
        self, target: Path, scan_progress_listener: BaseScanProgressListener | None
    ) -> ScannedDirectory:
        if not target.exists():
            raise FileNotFoundError(
                f"Project structure audit target does not exist: {target}"
            )
        if not target.is_dir():
            raise ValueError(
                f"Project structure audit target must be a directory: {target}"
            )
        return self._target_scanner.scan_directory(target, scan_progress_listener)

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


def _yield_unit_and_nested_units(unit: AuditableUnit) -> Iterator[AuditableUnit]:
    """Yield ``unit``, then every unit nested inside it, parents before children."""
    yield unit
    for child in unit.children():
        yield from _yield_unit_and_nested_units(child)
