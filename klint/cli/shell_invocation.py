"""Running a klint command with the arguments the shell passed."""

import asyncio
import sys
import traceback

from klint.app import AppSettings
from klint.app.pipeline import AuditPipeline
from klint.cli.exit_code import ExitCode
from klint.cli.runner import (
    AuditCommand,
    AuditCommandApp,
    parse_command_arguments,
    print_error_line,
    print_klint_warnings_raised_inside,
)
from klint.cli.wiring import create_command_injector


async def run_command_from_shell(command: AuditCommand) -> ExitCode:
    """Run ``command`` with the arguments the shell passed; return the exit code.

    An error the command does not expect is printed with its traceback, and
    the command exits with RUN_ERROR: exit 1 says that problems were found,
    so a crash must not end with it.
    """
    try:
        return await _run_command(command)
    except Exception as error:
        traceback.print_exc()
        print_error_line(command, f"unexpected {type(error).__name__}: {error}")
        return ExitCode.RUN_ERROR


async def _run_command(command: AuditCommand) -> ExitCode:
    try:
        with print_klint_warnings_raised_inside(command):
            arguments = parse_command_arguments(command, sys.argv[1:])
            settings = await asyncio.to_thread(
                AppSettings.from_env, arguments.target, arguments.custom_rules_path
            )
            injector = create_command_injector(settings)
            audit_pipeline = injector.get(AuditPipeline)
    except (OSError, ValueError) as error:
        # The command cannot be set up, for example a config or data file is
        # not valid.
        print_error_line(command, error)
        return ExitCode.RUN_ERROR
    print(f"[{command.name}] Judge: {settings.describe_judge()}", file=sys.stderr)
    app = AuditCommandApp(command, audit_pipeline)
    return await app.run_with_arguments(arguments)
