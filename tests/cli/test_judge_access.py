"""The klint command when the judge's endpoint refuses its API key."""

import asyncio
from pathlib import Path

import pytest

from klint.cli.exit_code import ExitCode
from klint.cli.file_audit import FILE_AUDIT_COMMAND
from klint.infra.system_one.http_judge import HttpSystemOneJudge
from tests.support.builders import build_audit_command_app, write_text
from tests.support.stub_system_one_server import StubSystemOneServer

SECRET_KEY = "sk-test-not-a-real-key"


@pytest.mark.parametrize(
    ("api_key", "status", "reason"),
    [
        (None, 403, "needs an API key, and none was given (HTTP 403: Forbidden)"),
        (SECRET_KEY, 401, "did not accept the API key (HTTP 401: Unauthorized)"),
        (SECRET_KEY, 403, "did not accept the API key (HTTP 403: Forbidden)"),
    ],
)
def test_refused_api_key_is_named_and_stops_the_run(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    system_one_server: StubSystemOneServer,
    api_key: str | None,
    status: int,
    reason: str,
) -> None:
    target = tmp_path / "a.py"
    write_text(target, "x = 1\n")
    system_one_server.response_status = status
    judge = HttpSystemOneJudge(
        model_name="jev-latest", base_url=system_one_server.base_url, api_key=api_key
    )
    app = build_audit_command_app(FILE_AUDIT_COMMAND, judge)

    exit_code = asyncio.run(app.run([str(target), "--json"]))

    captured = capsys.readouterr()
    endpoint = f"{system_one_server.base_url}/v1/systemone"
    assert exit_code == ExitCode.RUN_ERROR
    assert captured.out == ""
    assert captured.err.splitlines() == [
        f"[klint] Skipping {target}: the judge at {endpoint} {reason}",
        "[klint] Error: None of the 1 unit(s) to audit could be audited",
    ]
    assert SECRET_KEY not in captured.err
