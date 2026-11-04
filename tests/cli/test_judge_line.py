"""The line each command prints to say which judge it asks."""

import asyncio
import json
import sys
from pathlib import Path

import pytest

from klint.cli.change_summary_audit import CHANGE_SUMMARY_COMMAND
from klint.cli.exit_code import ExitCode
from klint.cli.file_audit import FILE_AUDIT_COMMAND
from klint.cli.runner import run_command_from_shell
from tests.support.builders import write_text
from tests.support.stub_system_one_server import StubSystemOneServer

SECRET_KEY = "sk-test-not-a-real-key"


@pytest.mark.parametrize(
    ("api_key", "key_note"), [(SECRET_KEY, "API key set"), (None, "no API key")]
)
def test_remote_judge_is_named_with_its_address_but_not_its_key(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    shell_env: dict[str, str],
    capsys: pytest.CaptureFixture[str],
    system_one_server: StubSystemOneServer,
    api_key: str | None,
    key_note: str,
) -> None:
    target = write_text(tmp_path / "a.py", "x = 1\n")
    shell_env["KLINT_JUDGE_MODE"] = "remote"
    shell_env["KLINT_JUDGE_BASE_URL"] = system_one_server.base_url
    shell_env["KLINT_JUDGE_MODEL"] = "jev-latest"
    if api_key is not None:
        shell_env["KLINT_JUDGE_API_KEY"] = api_key
    monkeypatch.setattr(sys, "argv", ["klint", str(target), "--json"])

    exit_code = asyncio.run(run_command_from_shell(FILE_AUDIT_COMMAND))

    captured = capsys.readouterr()
    assert exit_code == ExitCode.NO_PROBLEMS
    assert captured.err.splitlines() == [
        f"[klint] Judge: jev-latest at {system_one_server.base_url} "
        f"(remote, {key_note})"
    ]
    assert SECRET_KEY not in captured.err
    # The line goes to stderr, so the JSON on stdout is unchanged.
    assert json.loads(captured.out)["examined_files"] == [str(target)]


def test_judge_line_comes_before_the_audit_stops(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    shell_env: dict[str, str],
    capsys: pytest.CaptureFixture[str],
) -> None:
    shell_env["KLINT_JUDGE_MODE"] = "remote"
    target = tmp_path / "absent.json"
    monkeypatch.setattr(sys, "argv", ["klint-change-summary", str(target)])

    exit_code = asyncio.run(run_command_from_shell(CHANGE_SUMMARY_COMMAND))

    judge_line, error_line = capsys.readouterr().err.splitlines()
    assert exit_code == ExitCode.RUN_ERROR
    assert judge_line == (
        "[klint-change-summary] Judge: jaredpalmer/kev-4b at "
        "http://127.0.0.1:8009 (remote, no API key)"
    )
    assert error_line.startswith("[klint-change-summary] Error: ")
