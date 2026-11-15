"""The audit_files tool of klint-mcp: the file audit, as `klint --json` reports it."""

import asyncio
import json
from pathlib import Path
from typing import Any

import pytest

from klint.app import AppSettings
from klint.cli import FILE_AUDIT_COMMAND
from klint.mcp import create_mcp_server
from tests.mcp.conftest import CART_SOURCE
from tests.support.builders import build_audit_command_app, write_json, write_text
from tests.support.fakes import FakeJudge, JudgeBindingOverride
from tests.support.git_repository import run_git
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
    assert call.read_content() == expected
    assert expected["examined_files"] == [
        "cart.py",
        "cart.py::Cart",
        "cart.py::Cart.total",
        "cart.py::load",
    ]
    assert [finding["rule_id"] for finding in expected["findings"]] == ["tidy_file"]
    assert expected["judge_usage"] == {"requests": 4, "input_tokens": None}


def test_diff_audits_the_staged_change_of_the_working_directory(
    repository: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    # The total method gains a line; the file, the class and the method are
    # the units on the changed lines.
    changed = CART_SOURCE.replace(
        "        return sum(len(item) for item in self.items)\n",
        "        prices = [len(item) for item in self.items]\n"
        "        return sum(prices)\n",
    )
    write_text(repository / "cart.py", changed)
    run_git(repository, "add", "cart.py")
    server = create_mcp_server(repository, JudgeBindingOverride(FakeJudge()))

    call = call_tool(server, "audit_files", {"diff": True})

    expected = _run_cli_json(FakeJudge(), "--diff", capsys=capsys)
    assert not call.result.is_error
    assert call.read_content() == expected
    assert expected["examined_files"] == [
        "cart.py",
        "cart.py::Cart",
        "cart.py::Cart.total",
    ]
    assert expected["staged_change"]["diff_units"] == "units"


def test_diff_units_chooses_the_units_of_each_changed_file(
    repository: Path,
) -> None:
    write_text(repository / "cart.py", CART_SOURCE + "\n")
    run_git(repository, "add", "cart.py")
    judge = FakeJudge()
    server = create_mcp_server(repository, JudgeBindingOverride(judge))

    call = call_tool(server, "audit_files", {"diff": True, "diff_units": "all"})

    content = call.read_content()
    assert content["examined_files"] == [
        "cart.py",
        "cart.py::Cart",
        "cart.py::Cart.total",
        "cart.py::load",
    ]
    assert content["staged_change"]["diff_units"] == "all"


def test_a_path_with_diff_is_refused(repository: Path) -> None:
    server = create_mcp_server(repository, JudgeBindingOverride(FakeJudge()))

    call = call_tool(server, "audit_files", {"path": "cart.py", "diff": True})

    assert call.result.is_error
    assert "diff takes no path" in call.read_error()


def test_min_confidence_and_all_answers_are_passed_on(project: Path) -> None:
    server = create_mcp_server(
        project, JudgeBindingOverride(FakeJudge(default="pass", confidence=0.6))
    )

    hidden = call_tool(server, "audit_files", {"path": "cart.py"})
    shown = call_tool(
        server,
        "audit_files",
        {"path": "cart.py", "all_answers": True, "min_confidence": 0.5},
    )
    too_low = call_tool(
        server,
        "audit_files",
        {"path": "cart.py", "all_answers": True, "min_confidence": 0.7},
    )

    assert hidden.read_content()["findings"] == []
    assert sorted(
        (finding["rule_id"], finding["answer"])
        for finding in shown.read_content()["findings"]
    ) == [
        ("focused", "Pass"),
        ("short", "Pass"),
        ("short", "Pass"),
        ("tidy_file", "Pass"),
    ]
    assert too_low.read_content()["findings"] == []


def test_custom_rules_merge_over_the_packs(project: Path) -> None:
    write_json(
        project / "more_rules.json",
        {"documented": {"type": "choice", "question": "Is it documented?"}},
    )
    judge = FakeJudge()
    server = create_mcp_server(project, JudgeBindingOverride(judge))

    call = call_tool(
        server, "audit_files", {"path": "cart.py", "rules_path": "more_rules.json"}
    )

    assert not call.result.is_error
    assert judge.map_subject_to_asked_rule_ids()[CART_SOURCE] == {
        "documented",
        "tidy_file",
    }
