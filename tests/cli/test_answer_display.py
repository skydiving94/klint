"""How the terminal report shows an answer: from its scale, never its label."""

import asyncio
from pathlib import Path

import pytest

from klint.cli.exit_code import ExitCode
from klint.cli.file_audit import FILE_AUDIT_COMMAND
from klint.cli.runner import AuditCommandApp
from tests.support.builders import (
    FILE_RULE,
    build_audit_command_app,
    make_settings,
    write_json,
    write_text,
)
from tests.support.fakes import FakeJudge
from tests.support.notes_suite import NOTES_COMMAND, add_the_notes_suite

Capture = pytest.CaptureFixture[str]

BOLD, DIM, RESET = "\033[1m", "\033[2m", "\033[0m"
RED, GREEN, YELLOW = "\033[91m", "\033[92m", "\033[93m"
# A bar at 90% confidence, coloured with the given colour.
BAR_AT_90 = "█" * 9 + "░"


def _bar(color: str) -> str:
    return f"{color}{BAR_AT_90}{RESET} {BOLD} 90.0%{RESET}"


def _run_report(app: AuditCommandApp, target: Path, capsys: Capture) -> str:
    asyncio.run(app.run([str(target), "--all-answers"]))
    return capsys.readouterr().out


def _line_of(report: str, rule_id: str) -> str:
    (line,) = [line for line in report.splitlines() if f"{rule_id}{RESET}" in line]
    return line


def test_default_scale_keeps_its_badges_and_colours_only_problem_bars(
    tmp_path: Path, fake_judge: type[FakeJudge], capsys: Capture
) -> None:
    rule_id_to_answer = {
        "r_fail": "fail",
        "r_lack": "lack_of_evidence",
        "r_pass": "pass",
        "r_irrelevant": "irrelevant",
    }
    pack = write_json(
        tmp_path / "rules.json", {rule_id: FILE_RULE for rule_id in rule_id_to_answer}
    )
    target = write_text(tmp_path / "a.py", "x = 1\n")
    app = build_audit_command_app(
        FILE_AUDIT_COMMAND,
        fake_judge(choices=dict(rule_id_to_answer)),
        make_settings(built_in_rule_packs=[pack]),
    )

    report = _run_report(app, target, capsys)

    rule_id_to_start_and_bar = {
        rule_id: (
            _line_of(report, rule_id).split(f" {BOLD}{rule_id}")[0].strip(),
            _line_of(report, rule_id).split("Confidence: ")[1],
        )
        for rule_id in rule_id_to_answer
    }
    assert rule_id_to_start_and_bar == {
        "r_fail": (f"{BOLD}{RED}[FAIL]{RESET}", _bar(RED)),
        "r_lack": (f"{BOLD}{YELLOW}[LACK OF EVIDENCE]{RESET}", _bar(DIM)),
        "r_pass": (f"{BOLD}{GREEN}[PASS]{RESET}", _bar(DIM)),
        "r_irrelevant": (f"{DIM}[IRRELEVANT]{RESET}", _bar(DIM)),
    }
    # The order is that of the scale's sort ranks.
    assert [
        rule_id
        for line in report.splitlines()
        for rule_id in rule_id_to_answer
        if f"{rule_id}{RESET}" in line
    ] == ["r_fail", "r_lack", "r_pass", "r_irrelevant"]


@pytest.mark.parametrize(
    ("answer", "badge", "bar_color", "failure_count", "exit_code"),
    [
        ("rude", f"{BOLD}{RED}[RUDE]{RESET}", RED, 2, ExitCode.PROBLEMS_FOUND),
        ("polite", f"{BOLD}{GREEN}[POLITE]{RESET}", DIM, 0, ExitCode.NO_PROBLEMS),
    ],
)
def test_answer_of_another_scale_is_shown_as_its_scale_says(
    tmp_path: Path,
    fake_judge: type[FakeJudge],
    capsys: Capture,
    answer: str,
    badge: str,
    bar_color: str,
    failure_count: int,
    exit_code: ExitCode,
) -> None:
    write_text(tmp_path / "a.txt", "Thank you!\n")
    write_text(tmp_path / "b.txt", "Go away.\n")
    app = build_audit_command_app(
        NOTES_COMMAND,
        fake_judge(default=answer),
        binding_overrides=[add_the_notes_suite],
    )

    code = asyncio.run(app.run([str(tmp_path), "--all-answers"]))
    report = capsys.readouterr().out

    lines = [line for line in report.splitlines() if "polite_note" in line]
    assert len(lines) == 2
    assert all(line.strip().startswith(badge) for line in lines)
    assert all(line.endswith(_bar(bar_color)) for line in lines)
    assert f"{failure_count} failure(s)" in report
    assert code == exit_code
