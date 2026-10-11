import argparse
import asyncio
import sys
from collections.abc import Sequence
from pathlib import Path

from src.app.settings import AppSettings
from src.app.usecases.audit_path import AuditPath
from src.app.wiring import create_project_audit_path
from src.cli.runner import CommandStyle, print_error_line, run_audit_command

_STYLE = CommandStyle(
    name="klint-project",
    target_label="directories",
    json_key="examined_directories",
)


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="klint - recursive project structure audit CLI"
    )
    parser.add_argument(
        "directory", type=Path, help="Path to the project directory to audit"
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
        help="Output all judgments instead of fails only",
    )
    parser.add_argument(
        "--min-confidence",
        type=float,
        default=0.0,
        help="Minimum confidence to report an issue",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output raw JSON instead of formatted terminal report",
    )
    return parser.parse_args(argv)


class ProjectAuditCLIApp:
    def __init__(
        self,
        audit_path: AuditPath,
        default_custom_rules: Path | None = None,
    ) -> None:
        self._audit_path = audit_path
        self._default_custom_rules = default_custom_rules

    async def run(self, argv: Sequence[str] | None = None) -> int:
        args = _parse_args(argv)
        return await run_audit_command(
            self._audit_path,
            _STYLE,
            target=args.directory,
            rules_source=args.rules or self._default_custom_rules,
            show_all=args.all,
            min_confidence=args.min_confidence,
            as_json=args.json,
        )


async def main() -> int:
    args = _parse_args(sys.argv[1:])
    settings = await asyncio.to_thread(AppSettings.from_env, args.directory, args.rules)
    try:
        audit_path = create_project_audit_path(settings)
    except (OSError, ValueError) as error:
        # The command cannot be set up, for example a data file is not valid.
        print_error_line(_STYLE, error)
        return 1
    app = ProjectAuditCLIApp(
        audit_path=audit_path,
        default_custom_rules=settings.discovered_config_path,
    )
    return await app.run(sys.argv[1:])


def cli_main() -> int:
    return asyncio.run(main())


if __name__ == "__main__":
    sys.exit(cli_main())
