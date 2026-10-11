"""Ready-made rules, answers, settings and objects for tests to start from."""

import asyncio
import json
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from src import catalog
from src.app.settings import AppSettings
from src.app.wiring import FileAuditor, ProjectAuditor, create_injector
from src.catalog.code.common.extractors.project import RecursiveProjectExtractor
from src.catalog.code.common.units.directory import AuditableDirectoryUnit
from src.catalog.code.python.units.package import AuditablePythonPackageUnit
from src.catalog.common.file_traits_identifiers.extension_identifier import (
    ExtensionFileTraitsIdentifier,
)
from src.catalog.common.scales.pass_fail import PASS_FAIL_SCALE
from src.core.auditor import Auditor
from src.core.interfaces.file_traits_identifier import BaseFileTraitsIdentifier
from src.core.interfaces.judge import BaseJudge
from src.core.registry import UnitRegistry
from src.infra.language_to_file_extensions_loader.json_loader import (
    load_file_extension_to_language,
)
from tests.support.fakes import JudgeOverride
from tests.support.paths import (
    DEFAULT_LANGUAGE_TO_FILE_EXTENSIONS,
    DEFAULT_PROJECT_RULES,
    DEFAULT_RULE_PACKS,
)

RuleSpec = dict[str, Any]

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
    rules_paths: Sequence[Path] = DEFAULT_RULE_PACKS,
    project_rules_paths: Sequence[Path] = (DEFAULT_PROJECT_RULES,),
    kev_mode: str = "remote",
    language_to_file_extensions_path: Path = DEFAULT_LANGUAGE_TO_FILE_EXTENSIONS,
) -> AppSettings:
    """Return settings that point at the given rule packs and data files."""
    return AppSettings(
        model_name="fake",
        default_rules_paths=tuple(rules_paths),
        kev_mode=kev_mode,
        default_project_rules_paths=tuple(project_rules_paths),
        language_to_file_extensions_path=language_to_file_extensions_path,
    )


def file_auditor(rules_path: Path, judge: BaseJudge) -> Auditor:
    """Return klint's file auditor with one rule pack and the given judge."""
    settings = make_settings(rules_paths=(rules_path,))
    return create_injector(settings, JudgeOverride(judge)).get(FileAuditor)


def project_auditor(rules_path: Path, judge: BaseJudge) -> Auditor:
    """Return klint's project auditor with one rule pack and the given judge."""
    settings = make_settings(project_rules_paths=(rules_path,))
    return create_injector(settings, JudgeOverride(judge)).get(ProjectAuditor)


def build_file_traits_identifier() -> BaseFileTraitsIdentifier:
    """Return an identifier that knows the built-in languages."""
    return ExtensionFileTraitsIdentifier(
        load_file_extension_to_language(DEFAULT_LANGUAGE_TO_FILE_EXTENSIONS)
    )


def build_project_extractor() -> RecursiveProjectExtractor:
    """Return klint's project extractor, built the way the commands build it."""
    return create_injector(make_settings()).get(RecursiveProjectExtractor)


def extract_project(target: Path) -> AuditableDirectoryUnit:
    """Extract ``target`` and return the one directory unit for its root."""
    (unit,) = asyncio.run(build_project_extractor().extract(target))
    assert isinstance(unit, AuditableDirectoryUnit)
    return unit


def extract_python_project(target: Path) -> AuditablePythonPackageUnit:
    """Extract ``target``, which holds Python, and return its root package unit."""
    unit = extract_project(target)
    assert isinstance(unit, AuditablePythonPackageUnit)
    return unit
