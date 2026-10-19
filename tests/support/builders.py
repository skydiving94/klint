"""Ready-made rules, answers, settings and objects for tests to start from."""

import asyncio
import json
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

from klint import catalog
from klint.app.audit_pipeline import AuditPipeline
from klint.app.settings import AppSettings
from klint.app.wiring import Override, create_injector
from klint.catalog.code.common.extractors.project import RecursiveProjectExtractor
from klint.catalog.code.common.units.directory import AuditableDirectoryUnit
from klint.catalog.code.python.units.package import AuditablePythonPackageUnit
from klint.catalog.common.scales.pass_fail import PASS_FAIL_SCALE
from klint.catalog.common.scanners.target_scanner import TargetScanner
from klint.cli.runner import AuditCommand, AuditCommandApp
from klint.core.interfaces.judge import BaseJudge
from klint.core.models.judge_exchange import JudgeQuestion, JudgeRequest
from klint.core.models.question_type import QuestionType
from klint.core.registry import UnitRegistry
from klint.infra.language_to_file_extensions_loader.json_loader import (
    load_file_extension_to_language,
)
from tests.support.fakes import JudgeOverride
from tests.support.paths import (
    DEFAULT_LANGUAGE_TO_FILE_EXTENSIONS,
    TIDY_RULE_PACK,
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


def build_judge_request(subject: str, *question_ids: str) -> JudgeRequest:
    """Return a request asking each of ``question_ids`` about ``subject``.

    Each question has the type and answers of the default scale, and asks
    "Is <question_id> done?".
    """
    return JudgeRequest(
        subject=subject,
        questions=tuple(
            JudgeQuestion(
                question_id=question_id,
                question_type=QuestionType.CHOICE,
                question=f"Is {question_id} done?",
                choice_key_to_criterion=PASS_FAIL_SCALE.criteria_payload(),
            )
            for question_id in question_ids
        ),
    )


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
    built_in_rule_packs: Sequence[Path] = (TIDY_RULE_PACK,),
    fallback_rule_packs: Sequence[Path] = (TIDY_RULE_PACK,),
    file_contents_rule_pack_override: Path | None = None,
    project_structure_rule_pack_override: Path | None = None,
    kev_mode: str = "remote",
    language_to_file_extensions_path: Path = DEFAULT_LANGUAGE_TO_FILE_EXTENSIONS,
) -> AppSettings:
    """Return settings that point at the given rule packs and data files.

    The rule packs default to the tests' own, so that every file and every
    directory is asked a rule; a test that needs other packs passes them.
    """
    return AppSettings(
        model_name="fake",
        kev_mode=kev_mode,
        built_in_rule_packs=tuple(built_in_rule_packs),
        fallback_rule_packs=tuple(fallback_rule_packs),
        file_contents_rule_pack_override=file_contents_rule_pack_override,
        project_structure_rule_pack_override=project_structure_rule_pack_override,
        language_to_file_extensions_path=language_to_file_extensions_path,
    )


def build_audit_pipeline(
    judge: BaseJudge,
    settings: AppSettings | None = None,
    *,
    overrides: Sequence[Override] = (),
) -> AuditPipeline:
    """Return klint's audit pipeline, built as the commands build it.

    ``judge`` stands in for the model, and ``settings`` default to those of
    make_settings. ``overrides`` replace or add further bindings.
    """
    injector = create_injector(
        settings or make_settings(), JudgeOverride(judge), *overrides
    )
    return injector.get(AuditPipeline)


def build_audit_command_app(
    command: AuditCommand,
    judge: BaseJudge,
    settings: AppSettings | None = None,
    *,
    overrides: Sequence[Override] = (),
) -> AuditCommandApp:
    """Return the app of ``command``, built as the command builds it.

    The arguments are those of build_audit_pipeline.
    """
    return AuditCommandApp(
        command, build_audit_pipeline(judge, settings, overrides=overrides)
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
