"""The audit tools on a diff given as diff_text, as the commands audit --diff-from."""

import asyncio
import json
from pathlib import Path
from typing import Any

import pytest

from klint.app import AppSettings
from klint.cli import FILE_AUDIT_COMMAND, STRUCTURE_AUDIT_COMMAND
from klint.cli.audit_command import AuditCommand
from klint.mcp import create_mcp_server
from tests.mcp.conftest import CART_SOURCE
from tests.support.builders import build_audit_command_app, write_text
from tests.support.fakes import FakeJudge, JudgeBindingOverride
from tests.support.git_repository import run_git
from tests.support.mcp_client import call_tool

# The total method gains a line, so that the file, the class and the method
# are the units on the changed lines.
CHANGED_CART_SOURCE = CART_SOURCE.replace(
    "        return sum(len(item) for item in self.items)\n",
    "        prices = [len(item) for item in self.items]\n        return sum(prices)\n",
)


def _write_change(repository: Path) -> str:
    """Change the cart and add a package; return the diff git prints for it."""
    write_text(repository / "cart.py", CHANGED_CART_SOURCE)
    write_text(repository / "app" / "__init__.py", "")
    run_git(repository, "add", "--intent-to-add", "app/__init__.py")
    return run_git(repository, "diff")


def _run_cli_json(
    command: AuditCommand,
    diff_text: str,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> dict[str, Any]:
    """Return what ``command`` prints with --diff-from and --json for the diff."""
    diff_file = write_text(tmp_path / "change.diff", diff_text)
    app = build_audit_command_app(command, FakeJudge(), AppSettings.from_env(Path(".")))
    asyncio.run(app.run(["--diff-from", str(diff_file), "--json"]))
    output: dict[str, Any] = json.loads(capsys.readouterr().out)
    return output


def test_audit_files_audits_the_diff_as_klint_diff_from_does(
    repository: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    diff_text = _write_change(repository)
    server = create_mcp_server(repository, JudgeBindingOverride(FakeJudge()))

    call = call_tool(server, "audit_files", {"diff_text": diff_text})

    expected = _run_cli_json(FILE_AUDIT_COMMAND, diff_text, tmp_path, capsys)
    assert call.read_content() == expected
    assert expected["examined_files"] == [
        "app/__init__.py",
        "cart.py",
        "cart.py::Cart",
        "cart.py::Cart.total",
    ]
    assert expected["diff_change"]["diff_units"] == "units"
    assert expected["judge_usage"]["requests"] == 4


def test_diff_units_chooses_the_units_of_the_diff(repository: Path) -> None:
    diff_text = _write_change(repository)
    server = create_mcp_server(repository, JudgeBindingOverride(FakeJudge()))

    call = call_tool(
        server, "audit_files", {"diff_text": diff_text, "diff_units": "file"}
    )

    content = call.read_content()
    assert content["examined_files"] == ["app/__init__.py", "cart.py"]
    assert content["diff_change"]["diff_units"] == "file"


def test_audit_structure_audits_the_diff_as_klint_structure_diff_from_does(
    repository: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    write_text(repository / "other" / "__init__.py", "")
    diff_text = _write_change(repository)
    server = create_mcp_server(repository, JudgeBindingOverride(FakeJudge()))

    call = call_tool(server, "audit_structure", {"diff_text": diff_text})

    expected = _run_cli_json(STRUCTURE_AUDIT_COMMAND, diff_text, tmp_path, capsys)
    assert call.read_content() == expected
    assert expected["examined_directories"] == [".", "app"]
    assert expected["diff_change"]["audited_directories"] == [".", "app"]


@pytest.mark.parametrize(
    ("tool", "arguments"),
    [
        ("audit_files", {"path": "cart.py", "diff_text": "x"}),
        ("audit_files", {"diff": True, "diff_text": "x"}),
        ("audit_structure", {"path": ".", "diff_text": "x"}),
    ],
)
def test_a_call_mixing_the_inputs_is_refused(
    project: Path, tool: str, arguments: dict[str, object]
) -> None:
    judge = FakeJudge()
    server = create_mcp_server(project, JudgeBindingOverride(judge))

    call = call_tool(server, tool, arguments)

    assert "are mutually exclusive" in call.read_error()
    assert judge.map_subject_to_asked_rule_ids() == {}


def test_a_diff_naming_a_file_outside_the_directory_is_refused(
    repository: Path,
) -> None:
    diff_text = (
        "diff --git a/../outside.py b/../outside.py\n"
        "--- a/../outside.py\n"
        "+++ b/../outside.py\n"
        "@@ -1 +1 @@\n"
        "-x = 1\n"
        "+x = 2\n"
    )
    server = create_mcp_server(repository, JudgeBindingOverride(FakeJudge()))

    call = call_tool(server, "audit_files", {"diff_text": diff_text})

    assert "outside.py" in call.read_error()
    assert "outside the current directory" in call.read_error()


def test_a_diff_over_2_mb_is_refused_with_the_limit(project: Path) -> None:
    server = create_mcp_server(project, JudgeBindingOverride(FakeJudge()))

    call = call_tool(server, "audit_files", {"diff_text": "+" * (2 * 1024 * 1024 + 1)})

    assert "over the limit of 2 MB" in call.read_error()
