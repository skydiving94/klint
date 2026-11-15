"""A full audit, as Self-Audit runs it, treats an acknowledged entry as rebutted."""

import asyncio
import json
from pathlib import Path

import pytest

from klint.app import AppSettings
from klint.cli import FILE_AUDIT_COMMAND, ExitCode
from klint.core.interfaces import BaseJudge
from tests.support.builders import build_audit_command_app
from tests.support.fakes import SubjectJudge
from tests.support.git_repository import isolate_git, run_git
from tests.support.pre_commit import (
    CART_AFTER,
    CART_CHANGED_AGAIN,
    find_total_source,
    read_entries,
    run_ack,
    run_gate,
    set_up_gate_repository,
    stage,
)

Capture = pytest.CaptureFixture[str]


@pytest.fixture
def repository(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, shell_env: dict[str, str]
) -> Path:
    """Return a repository, as the cwd, with the total finding acknowledged."""
    del shell_env
    isolate_git(monkeypatch, tmp_path)
    repository = set_up_gate_repository(monkeypatch, tmp_path)
    stage(repository, {"cart.py": CART_AFTER})
    run_gate(_build_judge())
    [entry] = read_entries(repository)
    run_ack(entry["id"], "--note", "total is as short as it gets")
    run_git(repository, "commit", "--quiet", "--message", "Acknowledged")
    return repository


def _build_judge() -> BaseJudge:
    return SubjectJudge(
        {find_total_source(cart): "fail" for cart in (CART_AFTER, CART_CHANGED_AGAIN)}
    )


def _run_klint(*options: str) -> ExitCode:
    """Run klint on the cwd's repository, with the gate's rules and a fresh judge."""
    app = build_audit_command_app(
        FILE_AUDIT_COMMAND, _build_judge(), AppSettings.from_env(Path.cwd())
    )
    return asyncio.run(app.run(list(options)))


def test_an_acknowledged_finding_is_not_reported_and_is_listed(
    repository: Path, capsys: Capture
) -> None:
    [entry] = read_entries(repository)

    exit_code = _run_klint("cart.py", "--json")

    output = json.loads(capsys.readouterr().out)
    assert exit_code == ExitCode.NO_PROBLEMS
    assert output["findings"] == []
    assert output["applied_acknowledgements"] == [
        {
            "entry_id": entry["id"],
            "rule_id": "short",
            "unit_id": "cart.py::Cart.total",
            "acknowledged_at": entry["acknowledged_at"],
            "note": "total is as short as it gets",
        }
    ]
    assert output["unit_id_to_roll_up_status"]["cart.py::Cart.total"] == "no_problem"


def test_the_terminal_report_names_each_acknowledged_finding(
    repository: Path, capsys: Capture
) -> None:
    [entry] = read_entries(repository)

    exit_code = _run_klint(".")

    output = capsys.readouterr().out
    assert exit_code == ExitCode.NO_PROBLEMS
    assert "No architectural or semantic issues found" in output
    assert "Findings acknowledged in the project's .klint/acknowledgements/:" in output
    assert (
        f"short\x1b[0m on cart.py::Cart.total ({entry['id']}): total is as short "
        "as it gets"
    ) in output


def test_once_the_code_changes_the_finding_is_reported_again(
    repository: Path, capsys: Capture
) -> None:
    (repository / "cart.py").write_text(CART_CHANGED_AGAIN, encoding="utf-8")

    exit_code = _run_klint("cart.py", "--json")

    output = json.loads(capsys.readouterr().out)
    assert exit_code == ExitCode.PROBLEMS_FOUND
    assert [finding["unit_id"] for finding in output["findings"]] == [
        "cart.py::Cart.total"
    ]
    assert "applied_acknowledgements" not in output


def test_a_malformed_entry_stops_the_audit_naming_the_file(
    repository: Path, capsys: Capture
) -> None:
    bad_entry = repository / ".klint" / "acknowledgements" / "bad.json"
    bad_entry.write_text("[]", encoding="utf-8")

    exit_code = _run_klint("cart.py", "--json")

    assert exit_code == ExitCode.RUN_ERROR
    assert capsys.readouterr().err.splitlines()[-1] == (
        f"[klint] Error: The acknowledgement log entry '{bad_entry}' cannot be "
        "read: must be a JSON object"
    )


def test_a_target_outside_any_repository_reads_no_log(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: Capture
) -> None:
    isolate_git(monkeypatch, tmp_path)
    set_up_gate_repository(monkeypatch, tmp_path)
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "cart.py").write_text(CART_AFTER, encoding="utf-8")
    monkeypatch.chdir(outside)

    exit_code = _run_klint("cart.py", "--json")

    assert exit_code == ExitCode.PROBLEMS_FOUND
    assert "applied_acknowledgements" not in json.loads(capsys.readouterr().out)
