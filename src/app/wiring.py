from src import catalog
from src.app.settings import AppSettings
from src.core.interfaces.judge import BaseJudge
from src.core.auditor import Auditor
from src.catalog.common.extractors.whole_file import WholeFileExtractor
from src.catalog.common.scales.pass_fail import PASS_FAIL_SCALE
from src.catalog.code.common.extractors.project import (
    RecursiveProjectExtractor,
)
from src.infra.system_one.remote import RemoteSystemOneJudge
from src.core.registry import UnitRegistry
from src.infra.rule_loader.json_loader import JsonRuleLoader


def _create_unit_registry() -> UnitRegistry:
    registry = UnitRegistry()
    catalog.register(registry)
    return registry


def _create_judge(settings: AppSettings) -> BaseJudge:
    if settings.kev_mode == "local":
        from src.infra.system_one.local import LocalKevJudge

        return LocalKevJudge(checkpoint=settings.model_name)
    return RemoteSystemOneJudge(
        model_name=settings.model_name,
        base_url=settings.kev_base_url,
        api_key=settings.kev_api_key,
    )


def create_auditor(settings: AppSettings) -> Auditor:
    return Auditor(
        extractor=WholeFileExtractor(),
        judge=_create_judge(settings),
        rule_loader=JsonRuleLoader(
            default_rules_paths=settings.default_rules_paths,
            unit_registry=_create_unit_registry(),
        ),
        scale=PASS_FAIL_SCALE,
    )


def create_project_auditor(settings: AppSettings) -> Auditor:
    if not settings.default_project_rules_paths:
        raise EnvironmentError(
            "KEV_DEFAULT_PROJECT_RULES_PATH must be set to use the project "
            "structure audit CLI (src/cli/project_audit.py)."
        )
    return Auditor(
        extractor=RecursiveProjectExtractor(),
        judge=_create_judge(settings),
        rule_loader=JsonRuleLoader(
            default_rules_paths=settings.default_project_rules_paths,
            unit_registry=_create_unit_registry(),
        ),
        scale=PASS_FAIL_SCALE,
    )
