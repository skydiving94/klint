"""Ready-made rules, answers, settings and objects for tests to start from."""

import asyncio
import json
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

from src import catalog
from src.app.settings import AppSettings
from src.app.wiring import create_injector
from src.catalog.code.common.extractors.project import RecursiveProjectExtractor
from src.catalog.code.common.units.directory import AuditableDirectoryUnit
from src.catalog.code.python.units.package import AuditablePythonPackageUnit
from src.catalog.common.scales.pass_fail import PASS_FAIL_SCALE
from src.catalog.common.scanners.target_scanner import TargetScanner
from src.core.registry import UnitRegistry
from src.infra.language_to_file_extensions_loader.json_loader import (
    load_file_extension_to_language,
)
from tests.support.paths import (
    BUILT_IN_RULE_PACKS,
    DEFAULT_LANGUAGE_TO_FILE_EXTENSIONS,
    FALLBACK_RULE_PACKS,
)

RuleSpec = dict[str, Any]
# Takes every permission away from a path and returns the path; see the
# make_unreadable fixture.
MakeUnreadable = Callable[[Path], Path]

# The languages a file can be identified as, from the built-in data file.
KNOWN_LANGUAGES = frozenset(
    load_file_extension_to_language(DEFAULT_LANGUAGE_TO_FILE_EXTENSIONS).values()
)

FILE_RULE: RuleSpec = {"type": "choice", "instructions": "Is it tidy?"}
DIR_RULE: RuleSpec = {**FILE_RULE, "target_unit_types": ["project_directory"]}


def build_unit_registry() -> UnitRegistry:
    """Return a registry holding the unit types of every built-in suite."""
    registry = UnitRegistry()
    catalog.register(registry)
    return registry


UNIT_REGISTRY = build_unit_registry()

# The four answers of the default scale, for building and checking findings.
PASS = PASS_FAIL_SCALE.choice("pass")
FAIL = PASS_FAIL_SCALE.choice("fail")
IRRELEVANT = PASS_FAIL_SCALE.choice("irrelevant")
LACK_OF_EVIDENCE = PASS_FAIL_SCALE.choice("lack_of_evidence")


def write_json(path: Path, data: dict[str, Any]) -> Path:
    """Write ``data`` to ``path`` as JSON and return the path."""
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def write_text(path: Path, text: str) -> Path:
    """Write ``text`` to ``path``, creating its folders, and return the path."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def make_settings(
    built_in_rule_packs: Sequence[Path] = BUILT_IN_RULE_PACKS,
    fallback_rule_packs: Sequence[Path] = FALLBACK_RULE_PACKS,
    file_contents_rule_pack_override: Path | None = None,
    project_structure_rule_pack_override: Path | None = None,
    kev_mode: str = "remote",
    language_to_file_extensions_path: Path = DEFAULT_LANGUAGE_TO_FILE_EXTENSIONS,
) -> AppSettings:
    """Return settings that point at the given rule packs and data files."""
    return AppSettings(
        model_name="fake",
        kev_mode=kev_mode,
        built_in_rule_packs=tuple(built_in_rule_packs),
        fallback_rule_packs=tuple(fallback_rule_packs),
        file_contents_rule_pack_override=file_contents_rule_pack_override,
        project_structure_rule_pack_override=project_structure_rule_pack_override,
        language_to_file_extensions_path=language_to_file_extensions_path,
    )


def build_target_scanner() -> TargetScanner:
    """Return klint's target scanner, built the way the commands build it."""
    return create_injector(make_settings()).get(TargetScanner)


def build_project_extractor() -> RecursiveProjectExtractor:
    """Return klint's project extractor, built the way the commands build it."""
    return create_injector(make_settings()).get(RecursiveProjectExtractor)


def extract_project(target: Path) -> AuditableDirectoryUnit:
    """Scan ``target``, extract it, and return the directory unit for its root."""
    scanned_target = build_target_scanner().scan_directory(target)
    return asyncio.run(build_project_extractor().extract(scanned_target))


def extract_python_project(target: Path) -> AuditablePythonPackageUnit:
    """Extract ``target``, which holds Python, and return its root package unit."""
    unit = extract_project(target)
    assert isinstance(unit, AuditablePythonPackageUnit)
    return unit
