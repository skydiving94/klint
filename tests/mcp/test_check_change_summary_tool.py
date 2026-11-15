"""The check_change_summary tool: `klint-change-summary --json` on a document."""

import asyncio
import json
from pathlib import Path
from typing import Any

import pytest

from klint.app import AppSettings
from klint.cli import CHANGE_SUMMARY_COMMAND
from klint.mcp import create_mcp_server
from tests.support.builders import build_audit_command_app, write_text
from tests.support.change_summary import GREETING_DOCUMENT, HypothesisJudge
from tests.support.fakes import JudgeBindingOverride
from tests.support.mcp_client import call_tool

_FALSE_IMPORT_HUNK = {"Removes the unused import": {"no_false_statement": "inaccurate"}}


def test_check_change_summary_returns_what_the_command_prints_with_json(
    project: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    write_text(project / "summaries.json", json.dumps(GREETING_DOCUMENT))
    server = create_mcp_server(
        project, JudgeBindingOverride(HypothesisJudge(_FALSE_IMPORT_HUNK))
    )

    call = call_tool(server, "check_change_summary", {"path": "summaries.json"})

    app = build_audit_command_app(
        CHANGE_SUMMARY_COMMAND,
        HypothesisJudge(_FALSE_IMPORT_HUNK),
        AppSettings.from_env(Path("summaries.json")),
    )
    asyncio.run(app.run(["summaries.json", "--json"]))
    expected: dict[str, Any] = json.loads(capsys.readouterr().out)
    assert not call.result.is_error
    assert call.read_content() == expected
    assert expected["examined_summaries"][:2] == ["./", "app/"]
    assert [finding["unit_id"] for finding in expected["findings"]] == [
        "app/greet.py#2"
    ]
