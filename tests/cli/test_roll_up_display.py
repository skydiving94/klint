"""How a command shows each unit's roll-up status, in JSON and in the terminal."""

import asyncio
import json
import re
from pathlib import Path

import pytest

from klint.cli.exit_code import ExitCode
from tests.support.builders import build_audit_command_app, write_text
from tests.support.fakes import SubjectJudge
from tests.support.outline_suite import (
    OUTLINE,
    OUTLINE_COMMAND,
    add_the_outline_suite,
)

Capture = pytest.CaptureFixture[str]
_ANSI_CODE = re.compile(r"\x1b\[[0-9;]*m")


def _run_outline_command(tmp_path: Path, capsys: Capture, *options: str) -> str:
    """Run the outline command on the outline, its section 1.1 failing."""
    outline = write_text(tmp_path / "outline.json", json.dumps(OUTLINE))
    app = build_audit_command_app(
        OUTLINE_COMMAND,
        SubjectJudge({"Section 1.1.": "fail"}),
        overrides=[add_the_outline_suite],
    )
    exit_code = asyncio.run(app.run([str(outline), *options]))
    assert exit_code == ExitCode.PROBLEMS_FOUND
    return capsys.readouterr().out


def test_json_lists_the_roll_up_status_of_each_audited_unit(
    tmp_path: Path, capsys: Capture
) -> None:
    output = json.loads(_run_outline_command(tmp_path, capsys, "--json"))

    assert output["unit_id_to_roll_up_status"] == {
        "book": "descendant_problem",
        "chapter 1": "descendant_problem",
        "section 1.1": "own_problem",
        "section 1.2": "no_problem",
        "chapter 2": "no_problem",
        "section 2.1": "no_problem",
    }
    assert [finding["unit_id"] for finding in output["findings"]] == ["section 1.1"]


def test_terminal_shows_every_ancestor_of_a_problem_with_its_status(
    tmp_path: Path, capsys: Capture
) -> None:
    report = _ANSI_CODE.sub("", _run_outline_command(tmp_path, capsys))

    targets = [line for line in report.splitlines() if line.startswith("Target:")]
    # Fails only: the units with no problem anywhere beneath are not shown.
    assert targets == [
        "Target: book [DESCENDANT PROBLEM]",
        "Target: chapter 1 [DESCENDANT PROBLEM]",
        "Target: section 1.1 [OWN PROBLEM]",
    ]
    assert report.count("A problem was found in a unit nested in it") == 2


def test_terminal_shows_no_problem_on_units_shown_with_all_answers(
    tmp_path: Path, capsys: Capture
) -> None:
    report = _ANSI_CODE.sub("", _run_outline_command(tmp_path, capsys, "--all"))

    assert "Target: section 2.1 [NO PROBLEM]" in report.splitlines()
    assert "A problem was found in a unit nested in it" not in report
