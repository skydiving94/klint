from src.config.settings import AppSettings
from src.core.services.audit_service import AuditService
from src.infrastructure.extractors.file_extractor import WholeFileExtractor
from src.infrastructure.kev.pretrained import PretrainedKevEvaluator
from src.infrastructure.rules.json_loader import JsonRuleLoader


def create_audit_service(settings: AppSettings) -> AuditService:
    return AuditService(
        extractor=WholeFileExtractor(),
        evaluator=PretrainedKevEvaluator(
            model_name=settings.model_name,
            base_url=settings.kev_base_url,
            api_key=settings.kev_api_key,
        ),
        rule_loader=JsonRuleLoader(
            default_rules_path=settings.default_rules_path
        ),
    )
