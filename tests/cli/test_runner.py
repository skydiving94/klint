"""What the two commands share: their arguments and how they start up."""

import asyncio
import sys
import warnings
from pathlib import Path

import pytest

from src.app.settings import AppSettings
from src.cli.basic_audit import FILE_AUDIT_COMMAND
from src.cli.project_audit import PROJECT_AUDIT_COMMAND
from src.cli.runner import (
    AuditCommand,
    parse_command_arguments,
    run_command_from_shell,
)
from src.core.klint_warning import KlintWarning
from tests.support.builders import make_settings, write_text

COMMANDS = [FILE_AUDIT_COMMAND, PROJECT_AUDIT_COMMAND]


@pytest.mark.parametrize("command", COMMANDS)
def test_both_commands_read_the_same_arguments(command: AuditCommand) -> None:
    args = parse_command_arguments(
        command,
        [
            "some/path",
            "--rules",
            "r.json",
            "--all",
            "--min-confidence",
            "0.5",
            "--json",
        ],
    )

    assert args.target == Path("some/path")
    assert args.rules == Path("r.json")
    assert (args.all, args.min_confidence, args.json) == (True, 0.5, True)


@pytest.mark.parametrize(
    ("command", "argument_name"),
    [(FILE_AUDIT_COMMAND, "file"), (PROJECT_AUDIT_COMMAND, "directory")],
)
def test_each_command_names_its_path_argument_in_the_help(
    command: AuditCommand, argument_name: str, capsys: pytest.CaptureFixture[str]
) -> None:
    with pytest.raises(SystemExit):
        parse_command_arguments(command, ["--help"])

    help_text = capsys.readouterr().out
    assert f" {argument_name}\n" in help_text
    assert command.description in help_text


@pytest.mark.usefixtures("shell_env")
def test_klint_json_that_cannot_be_read_stops_the_command_with_one_line(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    target = write_text(tmp_path / "project" / "a.py", "x = 1\n")
    config = write_text(tmp_path / "project" / "klint.json", "{not json")
    monkeypatch.setattr(sys, "argv", ["klint", str(target)])

    exit_code = asyncio.run(run_command_from_shell(FILE_AUDIT_COMMAND))

    captured = capsys.readouterr()
    assert exit_code == 1
    assert captured.out == ""
    assert captured.err.startswith(f"[klint] Error: '{config}' is not valid JSON")
    assert captured.err.count("\n") == 1


def test_warning_raised_while_settings_load_is_printed_before_the_command_goes_on(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def load_settings_with_a_warning(*_args: object) -> AppSettings:
        warnings.warn("a setting was ignored", KlintWarning, stacklevel=1)
        return make_settings()

    monkeypatch.setattr(AppSettings, "from_env", load_settings_with_a_warning)
    monkeypatch.setattr(sys, "argv", ["klint", str(tmp_path / "absent.py")])

    exit_code = asyncio.run(run_command_from_shell(FILE_AUDIT_COMMAND))

    # The command went on past the warning, as far as the missing target.
    assert exit_code == 1
    warning_line, error_line = capsys.readouterr().err.splitlines()
    assert warning_line == "[klint] Warning: a setting was ignored"
    assert error_line.startswith("[klint] Error: Audit target does not exist")
