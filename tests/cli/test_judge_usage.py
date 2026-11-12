"""The judge's usage each command reports after its report."""

import asyncio
import json
import sys
from pathlib import Path

import pytest

from klint.cli import (
    CHANGE_SUMMARY_COMMAND,
    FILE_AUDIT_COMMAND,
    STRUCTURE_AUDIT_COMMAND,
    AuditCommand,
    ExitCode,
    run_command_from_shell,
)
from tests.support.builders import write_text
from tests.support.change_summary import GREETING_DOCUMENT
from tests.support.stub_system_one_server import StubSystemOneServer

Capture = pytest.CaptureFixture[str]

INPUT_TOKENS_PER_REQUEST = 1_234


def _write_target(tmp_path: Path, command: AuditCommand) -> Path:
    """Write what ``command`` audits: a project, or a change-summary document."""
    if command is CHANGE_SUMMARY_COMMAND:
        return write_text(tmp_path / "summaries.json", json.dumps(GREETING_DOCUMENT))
    write_text(tmp_path / "project" / "a.py", "def greet() -> str:\n    return 'hi'\n")
    write_text(tmp_path / "project" / "pkg" / "b.py", "y = 2\n")
    return tmp_path / "project"


def _run(
    command: AuditCommand,
    target: Path,
    server: StubSystemOneServer,
    shell_env: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
    *options: str,
) -> ExitCode:
    """Run ``command`` from the shell on ``target``, asking the stub server."""
    shell_env["KLINT_JUDGE_MODE"] = "remote"
    shell_env["KLINT_JUDGE_BASE_URL"] = server.base_url
    monkeypatch.setattr(sys, "argv", [command.name, str(target), *options])
    return asyncio.run(run_command_from_shell(command))


@pytest.mark.parametrize(
    "command", [FILE_AUDIT_COMMAND, STRUCTURE_AUDIT_COMMAND, CHANGE_SUMMARY_COMMAND]
)
def test_each_command_ends_with_the_requests_sent_and_the_input_tokens_billed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    shell_env: dict[str, str],
    capsys: Capture,
    system_one_server: StubSystemOneServer,
    command: AuditCommand,
) -> None:
    system_one_server.response_body = {
        "answers": {},
        "usage": {"input_tokens": INPUT_TOKENS_PER_REQUEST, "output_tokens": 2},
    }
    target = _write_target(tmp_path, command)

    exit_code = _run(command, target, system_one_server, shell_env, monkeypatch)

    captured = capsys.readouterr()
    request_count = len(system_one_server.received)
    assert exit_code == ExitCode.NO_PROBLEMS
    assert request_count > 1
    # After the report, on stderr, so that the report on stdout is as before.
    assert captured.err.splitlines()[-1] == (
        f"[{command.name}] Judge usage: {request_count} requests, "
        f"{request_count * INPUT_TOKENS_PER_REQUEST:,} input tokens"
    )
    assert "Judge usage" not in captured.out


@pytest.mark.parametrize(
    ("usage", "is_reported"),
    [
        ({"input_tokens": INPUT_TOKENS_PER_REQUEST}, True),
        (None, False),
        ({"input_tokens": "many"}, False),
        ("1234 tokens", False),
    ],
    ids=["reported", "not_reported", "malformed_count", "malformed_usage"],
)
def test_json_report_adds_the_judge_usage_and_keeps_its_findings(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    shell_env: dict[str, str],
    capsys: Capture,
    system_one_server: StubSystemOneServer,
    usage: object,
    is_reported: bool,
) -> None:
    response_body: dict[str, object] = {"answers": {"tidy": {"choice": "fail"}}}
    if usage is not None:
        response_body["usage"] = usage
    system_one_server.response_body = response_body
    rules = write_text(
        tmp_path / "rules.json",
        json.dumps({"tidy": {"type": "choice", "question": "Is the file tidy?"}}),
    )
    target = write_text(tmp_path / "a.py", "x = 1\n")

    exit_code = _run(
        FILE_AUDIT_COMMAND,
        target,
        system_one_server,
        shell_env,
        monkeypatch,
        "--json",
        "--rules",
        str(rules),
    )

    captured = capsys.readouterr()
    report = json.loads(captured.out)
    request_count = len(system_one_server.received)
    input_tokens = request_count * INPUT_TOKENS_PER_REQUEST if is_reported else None
    # A usage the judge did not report as a count leaves the run as it was.
    assert exit_code == ExitCode.PROBLEMS_FOUND
    assert ("tidy", str(target)) in [
        (finding["rule_id"], finding["unit_id"]) for finding in report["findings"]
    ]
    assert report["judge_usage"] == {
        "requests": request_count,
        "input_tokens": input_tokens,
    }
    tokens_phrase = (
        "input tokens not reported"
        if input_tokens is None
        else f"{input_tokens:,} input tokens"
    )
    assert captured.err.splitlines()[-1] == (
        f"[klint] Judge usage: {request_count} "
        f"{'request' if request_count == 1 else 'requests'}, {tokens_phrase}"
    )


def test_run_that_asks_the_judge_nothing_reports_no_request(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    shell_env: dict[str, str],
    capsys: Capture,
    system_one_server: StubSystemOneServer,
) -> None:
    # An empty directory holds no unit to ask about.
    target = tmp_path / "empty"
    target.mkdir()

    exit_code = _run(
        FILE_AUDIT_COMMAND, target, system_one_server, shell_env, monkeypatch, "--json"
    )

    captured = capsys.readouterr()
    assert exit_code == ExitCode.NO_PROBLEMS
    assert system_one_server.received == []
    assert json.loads(captured.out)["judge_usage"] == {
        "requests": 0,
        "input_tokens": 0,
    }
    assert captured.err.splitlines()[-1] == (
        "[klint] Judge usage: 0 requests, 0 input tokens"
    )
