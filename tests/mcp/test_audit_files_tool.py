"""The audit_files tool of klint-mcp: the file audit, as `klint --json` reports it."""

import asyncio
import json
from pathlib import Path
from typing import Any

import pytest

from klint.app import AppSettings
from klint.cli import FILE_AUDIT_COMMAND
from klint.mcp import create_mcp_server
from tests.support.builders import build_audit_command_app
from tests.support.fakes import FakeJudge, JudgeBindingOverride
from tests.support.mcp_client import call_tool


def _run_cli_json(
    judge: FakeJudge, *argv: str, capsys: pytest.CaptureFixture[str]
) -> dict[str, Any]:
    """Return what the klint command prints with --json for ``argv``."""
    settings = AppSettings.from_env(Path(argv[0]))
    app = build_audit_command_app(FILE_AUDIT_COMMAND, judge, settings)
    asyncio.run(app.run([*argv, "--json"]))
    output: dict[str, Any] = json.loads(capsys.readouterr().out)
    return output


def test_audit_files_returns_what_the_command_prints_with_json(
    project: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    judge = FakeJudge(rule_id_to_answer={"tidy_file": "fail"}, confidence=0.8)
    server = create_mcp_server(project, JudgeBindingOverride(judge))

    call = call_tool(server, "audit_files", {"path": "cart.py"})

    expected = _run_cli_json(
        FakeJudge(rule_id_to_answer={"tidy_file": "fail"}, confidence=0.8),
        "cart.py",
        capsys=capsys,
    )
    assert not call.result.is_error
    assert call.result.structured_content == expected
    assert expected["examined_files"] == ["cart.py"]
    assert [finding["rule_id"] for finding in expected["findings"]] == ["tidy_file"]
    assert expected["judge_usage"] == {"requests": 1, "input_tokens": None}
