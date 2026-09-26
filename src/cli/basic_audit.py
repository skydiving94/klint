import sys
import argparse
import json
from pathlib import Path
from typing import Optional, Sequence

from src.core.services.audit_service import AuditService
from src.infrastructure.rules.json_loader import JsonRuleLoader
from src.infrastructure.kev.pretrained import PretrainedKevEvaluator
from src.infrastructure.extractors.file_extractor import WholeFileExtractor
from src.config.settings import AppSettings


class CLIApp:
    def __init__(self, audit_service: AuditService):
        self._audit_service = audit_service

    def run(self, argv: Optional[Sequence[str]] = None) -> int:
        parser = argparse.ArgumentParser(description="Kev Code Auditor CLP")
        parser.add_argument("file", type=Path,
                            help="Path to the code file to audit")
        parser.add_argument(
            "--rules",
            type=Path,
            default=None,
            help="Path to user-defined rules JSON file",
        )
        parser.add_argument(
            "--all",
            action="store_true",
            help="Output all judgments (Pass, Fail, Irrelevant) instead of fails only",
        )
        args = parser.parse_args(argv)

        report = self._audit_service.run_audit(
            target=args.file,
            custom_rules_source=args.rules,
        )
        issues = report.get_issues(fails_only=not args.all)
        print(json.dumps(issues, indent=2))
        return 0


def create_audit_service(settings: AppSettings) -> AuditService:
    return AuditService(
        extractor=WholeFileExtractor(),
        evaluator=PretrainedKevEvaluator(
            model_name=settings.model_name,
            base_url=settings.kev_base_url,
            api_key=settings.kev_api_key,
        ),
        rule_loader=JsonRuleLoader(
            default_rules_path=settings.default_rules_path),
    )


def main() -> int:
    settings = AppSettings.from_env()
    service = create_audit_service(settings)
    app = CLIApp(audit_service=service)
    return app.run(sys.argv[1:])


if __name__ == "__main__":
    sys.exit(main())
