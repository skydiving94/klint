import argparse
import asyncio
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

from src.app.wiring import create_audit_service
from src.catalog.common.extractors.file_collector import collect_target_files
from src.cli.formatter import AuditProgressReporter, format_audit_report
from src.app.settings import AppSettings
from src.core.models.report import AuditFinding, AuditReport
from src.core.auditor import AuditService

MAX_CONCURRENT_AUDITS = 8


def _parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="klint - Declarative Code Auditor CLI"
    )
    parser.add_argument(
        "file",
        type=Path,
        help="Path to the code file or directory to audit",
    )
    parser.add_argument(
        "--rules",
        type=Path,
        default=None,
        help="Path to user-defined rules JSON file",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Output all judgments (Pass, Fail, Irrelevant, Lack of Evidence) instead of fails only",
    )
    parser.add_argument(
        "--min-confidence",
        type=float,
        default=0.0,
        help="Minimum confidence threshold (0.0 to 1.0) required to report an issue",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output raw JSON instead of formatted terminal report",
    )
    return parser.parse_args(argv)


class CLIApp:
    def __init__(
        self,
        audit_service: AuditService,
        default_custom_rules: Optional[Path] = None,
    ):
        self._audit_service = audit_service
        self._default_custom_rules = default_custom_rules

    async def run(self, argv: Optional[Sequence[str]] = None) -> int:
        args = _parse_args(argv)
        rules_source = args.rules or self._default_custom_rules
        try:
            target_files = await asyncio.to_thread(
                collect_target_files, args.file
            )
            await self._audit_service._rule_loader.load_rules(rules_source)
        except (FileNotFoundError, ValueError, json.JSONDecodeError) as exc:
            print(f"[klint] Error: {exc}", file=sys.stderr)
            return 1

        progress = AuditProgressReporter(
            total=len(target_files), label="files", enabled=not args.json
        )
        progress.start()
        semaphore = asyncio.Semaphore(MAX_CONCURRENT_AUDITS)

        async def _audit_with_limit(file_path: Path) -> Optional[AuditReport]:
            async with semaphore:
                try:
                    return await self._audit_service.run_audit(
                        target=file_path,
                        custom_rules_source=rules_source,
                    )
                except Exception as exc:
                    progress.finish()
                    print(
                        f"[klint] Skipping {file_path}: {exc}", file=sys.stderr
                    )
                    return None
                finally:
                    progress.advance(str(file_path))

        reports = await asyncio.gather(
            *(_audit_with_limit(file_path) for file_path in target_files)
        )
        progress.finish()

        findings: List[AuditFinding] = [
            finding
            for report in reports
            if report is not None
            for finding in report.get_findings(
                fails_only=not args.all,
                min_confidence=args.min_confidence,
            )
        ]
        examined = [
            str(p)
            for p, report in zip(target_files, reports)
            if report is not None
        ]
        if args.json:
            print(
                json.dumps(
                    {
                        "examined_files": examined,
                        "issues": [finding.to_dict() for finding in findings],
                    },
                    indent=2,
                )
            )
        else:
            print(format_audit_report(examined, findings, target_label="files"))
        return 0


async def main() -> int:
    args = _parse_args(sys.argv[1:])
    settings = await asyncio.to_thread(
        AppSettings.from_env, args.file, args.rules
    )
    app = CLIApp(
        audit_service=create_audit_service(settings),
        default_custom_rules=settings.discovered_config_path,
    )
    return await app.run(sys.argv[1:])


def cli_main() -> int:
    return asyncio.run(main())


if __name__ == "__main__":
    sys.exit(cli_main())
