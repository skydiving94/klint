import argparse
import asyncio
import sys
from pathlib import Path
from typing import Optional, Sequence

from src.app.settings import AppSettings
from src.app.usecases.audit_path import AuditPath
from src.app.wiring import create_file_audit_path
from src.cli.runner import CommandStyle, run_audit_command

_STYLE = CommandStyle(name="klint", target_label="files", json_key="examined_files")


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
        audit_path: AuditPath,
        default_custom_rules: Optional[Path] = None,
    ) -> None:
        self._audit_path = audit_path
        self._default_custom_rules = default_custom_rules

    async def run(self, argv: Optional[Sequence[str]] = None) -> int:
        args = _parse_args(argv)
        return await run_audit_command(
            self._audit_path,
            _STYLE,
            target=args.file,
            rules_source=args.rules or self._default_custom_rules,
            show_all=args.all,
            min_confidence=args.min_confidence,
            as_json=args.json,
        )


async def main() -> int:
    args = _parse_args(sys.argv[1:])
    settings = await asyncio.to_thread(
        AppSettings.from_env, args.file, args.rules
    )
    app = CLIApp(
        audit_path=create_file_audit_path(settings),
        default_custom_rules=settings.discovered_config_path,
    )
    return await app.run(sys.argv[1:])


def cli_main() -> int:
    return asyncio.run(main())


if __name__ == "__main__":
    sys.exit(cli_main())
