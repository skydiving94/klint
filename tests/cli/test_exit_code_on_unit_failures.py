"""The exit code when the judge fails on units: 2 only when none was audited."""

import asyncio
import json
from pathlib import Path

import pytest

from klint.cli.exit_code import ExitCode
from klint.cli.file_audit import FILE_AUDIT_COMMAND
from klint.cli.runner import AuditCommand, AuditCommandApp
from klint.cli.structure_audit import STRUCTURE_AUDIT_COMMAND
from klint.core.interfaces.judge import BaseJudge
from tests.support.builders import build_audit_command_app, make_settings, write_text
from tests.support.fakes import FakeJudge, PickyJudge

Capture = pytest.CaptureFixture[str]


def _write_project(root: Path) -> None:
    """Write a project where "poison" is in one file and one directory listing.

    The file poison.py holds it, and only the root directory lists that file.
    """
    write_text(root / "poison.py", "poison = 1\n")
    write_text(root / "pkg" / "a.py", "y = 2\n")


def _build_app(command: AuditCommand, judge: BaseJudge) -> AuditCommandApp:
    return build_audit_command_app(command, judge)


def _run(app: AuditCommandApp, target: Path) -> ExitCode:
    return asyncio.run(app.run([str(target), "--json"]))


@pytest.mark.parametrize(
    ("command", "unit_paths"),
    [
        (FILE_AUDIT_COMMAND, ("pkg/a.py", "poison.py")),
        (STRUCTURE_AUDIT_COMMAND, ("", "pkg")),
    ],
)
def test_run_where_no_unit_could_be_audited_exits_2_with_one_error_line(
    tmp_path: Path, capsys: Capture, command: AuditCommand, unit_paths: tuple[str, ...]
) -> None:
    _write_project(tmp_path)
    # Every subject holds the empty string, so the judge fails on every unit.
    judge = PickyJudge(refuses="")

    exit_code = _run(_build_app(command, judge), tmp_path)

    captured = capsys.readouterr()
    *skipping_lines, last_line = captured.err.splitlines()
    assert exit_code == ExitCode.RUN_ERROR
    assert captured.out == ""
    assert sorted(skipping_lines) == sorted(
        f"[{command.name}] Skipping {tmp_path / path if path else tmp_path}: "
        "judge is down"
        for path in unit_paths
    )
    assert last_line == (
        f"[{command.name}] Error: None of the 2 unit(s) to audit could be audited"
    )


@pytest.mark.parametrize("command", [FILE_AUDIT_COMMAND, STRUCTURE_AUDIT_COMMAND])
@pytest.mark.parametrize(
    ("answer", "expected_exit_code"),
    [("fail", ExitCode.PROBLEMS_FOUND), ("pass", ExitCode.NO_PROBLEMS)],
)
def test_run_where_some_units_could_be_audited_keeps_its_exit_code(
    tmp_path: Path,
    capsys: Capture,
    command: AuditCommand,
    answer: str,
    expected_exit_code: ExitCode,
) -> None:
    _write_project(tmp_path)
    judge = PickyJudge(refuses="poison")
    judge.default = answer

    exit_code = _run(_build_app(command, judge), tmp_path)

    captured = capsys.readouterr()
    assert exit_code == expected_exit_code
    assert len(json.loads(captured.out)[command.audited_units_json_key]) == 1
    (skipping_line,) = captured.err.splitlines()
    assert skipping_line.startswith(f"[{command.name}] Skipping ")
    assert skipping_line.endswith(": judge is down")


@pytest.mark.parametrize("command", [FILE_AUDIT_COMMAND, STRUCTURE_AUDIT_COMMAND])
def test_run_with_no_unit_to_audit_exits_0(
    tmp_path: Path,
    fake_judge: type[FakeJudge],
    capsys: Capture,
    command: AuditCommand,
) -> None:
    _write_project(tmp_path)
    judge = fake_judge()
    # No rule applies to any unit, so no unit is selected.
    settings = make_settings(built_in_rule_packs=[], fallback_rule_packs=[])
    app = build_audit_command_app(command, judge, settings)

    exit_code = _run(app, tmp_path)

    captured = capsys.readouterr()
    assert exit_code == ExitCode.NO_PROBLEMS
    assert json.loads(captured.out) == {
        command.audited_units_json_key: [],
        "unit_id_to_roll_up_status": {},
        "findings": [],
    }
    assert captured.err == ""
    assert judge.requests == []
