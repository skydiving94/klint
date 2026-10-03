from src.app.settings import AppSettings
from src.core.interfaces.evaluator import BaseKevEvaluator
from src.core.auditor import AuditService
from src.infrastructure.extractors.file_extractor import WholeFileExtractor
from src.infrastructure.extractors.project_extractor import (
    RecursiveProjectExtractor,
)
from src.infra.system_one.remote import PretrainedKevEvaluator
from src.infra.rule_loader.json_loader import JsonRuleLoader


def _create_evaluator(settings: AppSettings) -> BaseKevEvaluator:
    if settings.kev_mode == "local":
        from src.infra.system_one.local import InProcessKevEvaluator

        return InProcessKevEvaluator(checkpoint=settings.model_name)
    return PretrainedKevEvaluator(
        model_name=settings.model_name,
        base_url=settings.kev_base_url,
        api_key=settings.kev_api_key,
    )


def create_audit_service(settings: AppSettings) -> AuditService:
    return AuditService(
        extractor=WholeFileExtractor(),
        evaluator=_create_evaluator(settings),
        rule_loader=JsonRuleLoader(
            default_rules_path=settings.default_rules_path
        ),
    )


def create_project_audit_service(settings: AppSettings) -> AuditService:
    if settings.default_project_rules_path is None:
        raise EnvironmentError(
            "KEV_DEFAULT_PROJECT_RULES_PATH must be set to use the project "
            "structure audit CLI (src/cli/project_audit.py)."
        )
    return AuditService(
        extractor=RecursiveProjectExtractor(),
        evaluator=_create_evaluator(settings),
        rule_loader=JsonRuleLoader(
            default_rules_path=settings.default_project_rules_path
        ),
    )
