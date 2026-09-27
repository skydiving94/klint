import argparse
import asyncio
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence
from src.cli.factory import create_audit_service
from src.cli.file_collector import collect_target_files
from src.config.settings import AppSettings
from src.core.services.audit_service import AuditService


def _parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Kev Code Auditor CLP")
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
        help="Output all judgments (Pass, Fail, Irrelevant) instead of fails only",
    )
    parser.add_argument(
        "--min-confidence",
        type=float,
        default=0.0,
        help="Minimum confidence threshold (0.0 to 1.0) required to report an issue",
    )
    return parser.parse_args(argv)


class CLIApp:
    def __init__(self, audit_service: AuditService):
        self._audit_service = audit_service

    async def run(self, argv: Optional[Sequence[str]] = None) -> int:
        args = _parse_args(argv)
        target_files = await asyncio.to_thread(collect_target_files, args.file)
        reports = await asyncio.gather(
            *(
                self._audit_service.run_audit(
                    target=file_path,
                    custom_rules_source=args.rules,
                )
                for file_path in target_files
            )
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
            "examined_files": [str(p) for p in target_files],
            "issues": issues,
        }
        print(json.dumps(output, indent=2))
        return 0


async def main() -> int:
    settings = await asyncio.to_thread(AppSettings.from_env)
    app = CLIApp(audit_service=create_audit_service(settings))
    return await app.run(sys.argv[1:])


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
