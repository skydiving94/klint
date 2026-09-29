import argparse
import asyncio
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

from src.cli.factory import create_project_audit_service
from src.cli.file_collector import collect_target_directories
from src.config.settings import AppSettings
from src.core.services.audit_service import AuditService

MAX_CONCURRENT_AUDITS = 8


def _parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="klint - recursive project structure audit CLI"
    )
    parser.add_argument(
        "directory", type=Path, help="Path to the project directory to audit"
    )
    parser.add_argument(
        "--rules", type=Path, default=None, help="Path to user-defined rules JSON file"
    )
    parser.add_argument(
        "--all", action="store_true", help="Output all judgments instead of fails only"
    )
    parser.add_argument(
        "--min-confidence",
        type=float,
        default=0.0,
        help="Minimum confidence to report an issue",
    )
    return parser.parse_args(argv)


class ProjectAuditCLIApp:
    def __init__(self, audit_service: AuditService):
        self._audit_service = audit_service

    async def run(self, argv: Optional[Sequence[str]] = None) -> int:
        args = _parse_args(argv)
        target_dirs = await asyncio.to_thread(
            collect_target_directories, args.directory
        )
        semaphore = asyncio.Semaphore(MAX_CONCURRENT_AUDITS)

        async def _audit_with_limit(dir_path: Path):
            async with semaphore:
                return await self._audit_service.run_audit(
                    target=dir_path,
                    custom_rules_source=args.rules,
                )

        reports = await asyncio.gather(
            *(_audit_with_limit(dir_path) for dir_path in target_dirs)
        )
        issues: List[Dict[str, Any]] = [
            issue
            for report in reports
            for issue in report.get_issues(
                fails_only=not args.all,
                min_confidence=args.min_confidence,
            )
        ]
        output = {
            "examined_directories": [str(d) for d in target_dirs],
            "issues": issues,
        }
        print(json.dumps(output, indent=2))
        return 0


async def main() -> int:
    settings = await asyncio.to_thread(AppSettings.from_env)
    app = ProjectAuditCLIApp(
        audit_service=create_project_audit_service(settings)
    )
    return await app.run(sys.argv[1:])


def cli_main() -> int:
    return asyncio.run(main())


if __name__ == "__main__":
    sys.exit(cli_main())
