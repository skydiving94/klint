"""What the two commands share: their arguments."""

from pathlib import Path

import pytest

from src.cli.basic_audit import FILE_AUDIT_COMMAND
from src.cli.project_audit import PROJECT_AUDIT_COMMAND
from src.cli.runner import AuditCommand, parse_command_arguments

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
