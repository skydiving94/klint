"""What the two commands share: their arguments and how they start up."""

import asyncio
import json
import sys
from collections.abc import Callable
from pathlib import Path

import pytest

from klint.cli import file_audit, structure_audit
from klint.cli.exit_code import ExitCode
from klint.cli.file_audit import FILE_AUDIT_COMMAND
from klint.cli.runner import (
    AuditCommand,
    parse_command_arguments,
    run_command_from_shell,
)
from klint.cli.structure_audit import STRUCTURE_AUDIT_COMMAND
from tests.support.builders import (
    DIR_RULE,
    FILE_RULE,
    build_audit_command_app,
    make_settings,
    write_json,
    write_text,
)
from tests.support.fakes import FakeJudge
from tests.support.stub_system_one_server import StubSystemOneServer


@pytest.mark.parametrize(
    ("command", "audited_path_parts", "rule_id"),
    [
        (FILE_AUDIT_COMMAND, ("a.py",), "for_files"),
        (STRUCTURE_AUDIT_COMMAND, (), "for_directories"),
    ],
)
def test_both_commands_take_the_same_options(
    tmp_path: Path,
    fake_judge: type[FakeJudge],
    capsys: pytest.CaptureFixture[str],
    command: AuditCommand,
    audited_path_parts: tuple[str, ...],
    rule_id: str,
) -> None:
    custom = write_json(
        tmp_path / "custom.json", {"for_files": FILE_RULE, "for_directories": DIR_RULE}
    )
    target = tmp_path / "pkg"
    write_text(target / "a.py", "x = 1\n")
    # No rule but the custom ones, each answered "pass" with low confidence.
    settings = make_settings(built_in_rule_packs=[], fallback_rule_packs=[])
    app = build_audit_command_app(command, fake_judge(confidence=0.4), settings)
    argv = [str(target), "--json", "--rules", str(custom), "--all"]

    asyncio.run(app.run(argv))
    every_judgment = json.loads(capsys.readouterr().out)
    asyncio.run(app.run([*argv, "--min-confidence", "0.5"]))
    confident_judgments = json.loads(capsys.readouterr().out)

    audited = str(target.joinpath(*audited_path_parts))
    assert every_judgment[command.audited_units_json_key] == [audited]
    assert [(i["rule_id"], i["answer"]) for i in every_judgment["findings"]] == [
        (rule_id, "Pass")
    ]
    assert confident_judgments == {
        command.audited_units_json_key: [audited],
        "unit_id_to_roll_up_status": {audited: "no_problem"},
        "findings": [],
    }


@pytest.mark.parametrize(
    ("command", "argument_name"),
    [(FILE_AUDIT_COMMAND, "file"), (STRUCTURE_AUDIT_COMMAND, "directory")],
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
    assert exit_code == ExitCode.RUN_ERROR
    assert captured.out == ""
    assert captured.err.startswith(f"[klint] Error: '{config}' is not valid JSON")
    assert captured.err.count("\n") == 1


@pytest.mark.usefixtures("shell_env")
def test_warning_raised_while_settings_load_is_printed_before_the_command_goes_on(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    # The project's klint.json, found in the working directory. The remote
    # judge is built but never asked, as the target is missing.
    write_json(
        Path.cwd() / "klint.json",
        {"env": {"KEV_MODE": "remote", "KEV_MODLE_NAME": "x"}},
    )
    target = tmp_path / "absent.py"
    monkeypatch.setattr(sys, "argv", ["klint", str(target)])

    exit_code = asyncio.run(run_command_from_shell(FILE_AUDIT_COMMAND))

    # The command went on past the warning, as far as the missing target.
    assert exit_code == ExitCode.RUN_ERROR
    warning_line, error_line = capsys.readouterr().err.splitlines()
    assert warning_line.startswith("[klint] Warning: ")
    assert "unknown keys ['KEV_MODLE_NAME']" in warning_line
    assert error_line.startswith("[klint] Error: Audit target does not exist")


@pytest.mark.parametrize("command", [FILE_AUDIT_COMMAND, STRUCTURE_AUDIT_COMMAND])
@pytest.mark.parametrize(
    ("judge_choice", "extra_argv", "expected_exit_code"),
    [
        ("pass", [], ExitCode.NO_PROBLEMS),
        ("pass", ["--all"], ExitCode.NO_PROBLEMS),
        ("lack_of_evidence", [], ExitCode.NO_PROBLEMS),
        ("fail", [], ExitCode.PROBLEMS_FOUND),
        ("fail", ["--json"], ExitCode.PROBLEMS_FOUND),
        # The fake judge answers with confidence 0.9.
        ("fail", ["--min-confidence", "0.95"], ExitCode.NO_PROBLEMS),
    ],
)
def test_exit_code_says_whether_a_failure_was_found(
    tmp_path: Path,
    fake_judge: type[FakeJudge],
    command: AuditCommand,
    judge_choice: str,
    extra_argv: list[str],
    expected_exit_code: ExitCode,
) -> None:
    target = tmp_path / "pkg"
    write_text(target / "a.py", "x = 1\n")
    app = build_audit_command_app(command, fake_judge(default=judge_choice))

    exit_code = asyncio.run(app.run([str(target), *extra_argv]))

    assert exit_code == expected_exit_code


@pytest.mark.parametrize("cli_main", [file_audit.cli_main, structure_audit.cli_main])
def test_command_that_cannot_run_exits_with_status_2(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    shell_env: dict[str, str],
    capsys: pytest.CaptureFixture[str],
    cli_main: Callable[[], int],
) -> None:
    shell_env["KEV_MODE"] = "remote"
    monkeypatch.setattr(sys, "argv", ["klint", str(tmp_path / "absent")])

    exit_code = cli_main()

    assert exit_code == 2
    assert "does not exist" in capsys.readouterr().err


@pytest.mark.parametrize("cli_main", [file_audit.cli_main, structure_audit.cli_main])
def test_command_line_that_cannot_be_parsed_exits_with_status_2(
    monkeypatch: pytest.MonkeyPatch, cli_main: Callable[[], int]
) -> None:
    monkeypatch.setattr(sys, "argv", ["klint", "--no-such-option"])

    with pytest.raises(SystemExit) as stopped:
        cli_main()

    assert stopped.value.code == ExitCode.RUN_ERROR


@pytest.mark.parametrize("cli_main", [file_audit.cli_main, structure_audit.cli_main])
def test_unknown_mode_stops_the_command_before_any_judge_is_built(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    shell_env: dict[str, str],
    capsys: pytest.CaptureFixture[str],
    cli_main: Callable[[], int],
) -> None:
    shell_env["KEV_MODE"] = "locl"
    monkeypatch.setattr(sys, "argv", ["klint", str(tmp_path)])

    exit_code = cli_main()

    (error_line,) = capsys.readouterr().err.splitlines()
    assert exit_code == ExitCode.RUN_ERROR
    assert "KEV_MODE 'locl'" in error_line
    assert "valid values: ['local', 'remote']" in error_line


@pytest.mark.usefixtures("shell_env")
def test_rules_flag_adds_to_the_rules_of_the_project_klint_json(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    system_one_server: StubSystemOneServer,
) -> None:
    target = write_text(tmp_path / "project" / "a.py", "x = 1\n")
    write_json(
        tmp_path / "project" / "klint.json",
        {
            "env": {
                "KEV_MODE": "remote",
                "KEV_BASE_URL": system_one_server.base_url,
                "KEV_MODEL_NAME": "from-klint-json",
            },
            "rules": {
                "shared": {**FILE_RULE, "instructions": "From klint.json?"},
                "project_only": FILE_RULE,
            },
        },
    )
    rules_file = write_json(
        tmp_path / "custom.json",
        {
            "env": {"KEV_MODEL_NAME": "from-rules-file"},
            "rules": {
                "shared": {**FILE_RULE, "instructions": "From --rules?"},
                "custom_only": FILE_RULE,
            },
        },
    )
    argv = ["klint", str(target), "--rules", str(rules_file), "--json"]
    monkeypatch.setattr(sys, "argv", argv)

    exit_code = asyncio.run(run_command_from_shell(FILE_AUDIT_COMMAND))

    assert exit_code == ExitCode.NO_PROBLEMS
    (warning_line,) = capsys.readouterr().err.splitlines()
    assert warning_line.startswith(f"[klint] Warning: The 'env' key in '{rules_file}'")
    # Settings come from klint.json only; the rules of both files are asked,
    # and those of --rules win by rule ID.
    (received,) = system_one_server.received
    assert isinstance(received.body, dict)
    assert received.body["model"] == "from-klint-json"
    rule_id_to_instructions = {
        rule_id: question["instructions"]
        for rule_id, question in received.body["questions"].items()
    }
    assert rule_id_to_instructions["shared"] == "From --rules?"
    assert {"project_only", "custom_only"} <= set(rule_id_to_instructions)
