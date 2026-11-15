"""The audit_structure tool: the structure audit, as `klint-structure --json` has it."""

import asyncio
import json
from pathlib import Path
from typing import Any

import pytest

from klint.app import AppSettings
from klint.cli import STRUCTURE_AUDIT_COMMAND
from klint.mcp import create_mcp_server
from tests.support.builders import build_audit_command_app, write_text
from tests.support.fakes import FakeJudge, JudgeBindingOverride
from tests.support.mcp_client import call_tool


def test_audit_structure_returns_what_the_command_prints_with_json(
    project: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    write_text(project / "app" / "__init__.py", "")
    write_text(project / "app" / "models.py", "x = 1\n")
    answers: dict[str, str | None] = {"tidy_directory": "fail"}
    server = create_mcp_server(
        project, JudgeBindingOverride(FakeJudge(rule_id_to_answer=answers))
    )

    call = call_tool(server, "audit_structure", {"path": "."})

    settings = AppSettings.from_env(Path("."))
    app = build_audit_command_app(
        STRUCTURE_AUDIT_COMMAND, FakeJudge(rule_id_to_answer=answers), settings
    )
    asyncio.run(app.run([".", "--json"]))
    expected: dict[str, Any] = json.loads(capsys.readouterr().out)
    assert not call.result.is_error
    assert call.read_content() == expected
    assert expected["examined_directories"] == [".", "app"]
    assert {finding["rule_id"] for finding in expected["findings"]} == {
        "tidy_directory"
    }


def test_audit_structure_rejects_a_file(project: Path) -> None:
    server = create_mcp_server(project, JudgeBindingOverride(FakeJudge()))

    call = call_tool(server, "audit_structure", {"path": "cart.py"})

    assert call.result.is_error
    assert "cart.py" in call.read_error()
