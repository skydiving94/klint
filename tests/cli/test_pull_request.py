"""klint-pull-request: the threshold and the combined report of a PR's check."""

import asyncio
import json
from pathlib import Path
from typing import Any

import pytest

from klint.cli import STRUCTURE_AUDIT_COMMAND, ExitCode, run_pull_request_arguments
from tests.support.builders import (
    DIR_RULE,
    build_audit_command_app,
    make_settings,
    write_json,
)
from tests.support.cart_project import (
    FUNCTION_RULE,
    build_cart_settings,
    run_file_command,
)
from tests.support.fakes import FakeJudge
from tests.support.git_repository import isolate_git, run_git
from tests.support.pre_commit import (
    CART_AFTER,
    run_ack,
    run_gate,
    set_up_gate_repository,
    stage,
)

Capture = pytest.CaptureFixture[str]


def run_pull_request(*options: str) -> ExitCode:
    return asyncio.run(run_pull_request_arguments(list(options), Path.cwd()))


def audit_diff(judge: FakeJudge, tmp_path: Path, diff: Path, capsys: Capture) -> None:
    """Run both audits of ``diff`` at 0.8, writing their reports to ``tmp_path``."""
    capsys.readouterr()
    run_file_command(
        judge,
        build_cart_settings(tmp_path, short=FUNCTION_RULE),
        "--diff-from",
        str(diff),
        "--json",
        "--min-confidence",
        "0.8",
    )
    (tmp_path / "file.json").write_text(capsys.readouterr().out, encoding="utf-8")
    pack = write_json(tmp_path / "structure_rules.json", {"tidy_directory": DIR_RULE})
    settings = make_settings(built_in_rule_packs=[pack], fallback_rule_packs=[pack])
    app = build_audit_command_app(STRUCTURE_AUDIT_COMMAND, judge, settings)
    asyncio.run(
        app.run(["--diff-from", str(diff), "--json", "--min-confidence", "0.8"])
    )
    (tmp_path / "structure.json").write_text(capsys.readouterr().out, encoding="utf-8")


def report(tmp_path: Path) -> ExitCode:
    return run_pull_request(
        "report",
        "--file-report",
        str(tmp_path / "file.json"),
        "--structure-report",
        str(tmp_path / "structure.json"),
        "--min-confidence",
        "0.8",
        "--output",
        str(tmp_path / "findings.json"),
    )


def read_findings(tmp_path: Path) -> dict[str, Any]:
    findings: dict[str, Any] = json.loads(
        (tmp_path / "findings.json").read_text(encoding="utf-8")
    )
    return findings


@pytest.fixture
def repository(
    shell_env: dict[str, str], monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> Path:
    """Return a shop repository whose cart change is staged, diffed in change.diff.

    The settings come from ``shell_env``'s private environment alone.
    """
    del shell_env
    isolate_git(monkeypatch, tmp_path)
    repository = set_up_gate_repository(monkeypatch, tmp_path)
    stage(repository, {"cart.py": CART_AFTER})
    (tmp_path / "change.diff").write_text(
        run_git(repository, "diff", "--cached"), encoding="utf-8"
    )
    return repository


@pytest.mark.usefixtures("shell_env")
@pytest.mark.parametrize(
    ("model_name", "expected"),
    [
        ("jev-latest", "0.8"),
        ("jaredpalmer/kev-4b", "0.5"),
        ("jaredpalmer/kev-0.8b", "0.5"),
        ("some-other-model", "0.8"),
    ],
)
def test_the_threshold_is_the_judges_own_as_for_the_commit_gate(
    monkeypatch: pytest.MonkeyPatch, capsys: Capture, model_name: str, expected: str
) -> None:
    monkeypatch.setenv("KLINT_JUDGE_MODEL", model_name)

    exit_code = run_pull_request("threshold")

    assert exit_code == ExitCode.NO_PROBLEMS
    assert capsys.readouterr().out == f"{expected}\n"


@pytest.mark.usefixtures("shell_env")
def test_the_projects_commit_threshold_overrides_the_judges(
    monkeypatch: pytest.MonkeyPatch, capsys: Capture
) -> None:
    monkeypatch.setenv("KLINT_JUDGE_MODEL", "jev-latest")
    monkeypatch.setenv("KLINT_COMMIT_MIN_CONFIDENCE", "0.65")

    exit_code = run_pull_request("threshold")

    assert exit_code == ExitCode.NO_PROBLEMS
    assert capsys.readouterr().out == "0.65\n"


@pytest.mark.usefixtures("shell_env")
def test_a_threshold_that_is_not_a_number_cannot_run(
    monkeypatch: pytest.MonkeyPatch, capsys: Capture
) -> None:
    monkeypatch.setenv("KLINT_COMMIT_MIN_CONFIDENCE", "high")

    exit_code = run_pull_request("threshold")

    assert exit_code == ExitCode.RUN_ERROR
    assert "KLINT_COMMIT_MIN_CONFIDENCE 'high'" in capsys.readouterr().err


@pytest.mark.usefixtures("repository")
def test_the_report_combines_both_audits_findings(
    tmp_path: Path, capsys: Capture
) -> None:
    judge = FakeJudge(
        rule_id_to_answer={"short": "fail", "tidy_directory": "fail"}, confidence=0.91
    )
    audit_diff(judge, tmp_path, tmp_path / "change.diff", capsys)

    exit_code = report(tmp_path)

    summary = capsys.readouterr().out
    findings = read_findings(tmp_path)
    assert exit_code == ExitCode.PROBLEMS_FOUND
    assert findings["min_confidence"] == 0.8
    assert set(findings["reports"]) == {"file", "structure"}
    [file_finding] = [f for f in findings["findings"] if f["audit"] == "file"]
    [directory_finding] = [f for f in findings["findings"] if f["audit"] == "structure"]
    assert file_finding["unit_id"] == "cart.py::Cart.total"
    assert file_finding["acknowledge_command"].startswith("klint-ack ")
    assert directory_finding["unit_id"] == "."
    assert directory_finding["acknowledge_command"] is None
    assert "### klint: 2 findings in this pull request" in summary
    location = file_finding["location"]
    assert (
        f"| `cart.py` | {location['start_line']}-{location['end_line']} | `short` "
        f"| 0.91 | `{file_finding['acknowledge_command']}` |" in summary
    )
    assert "| `.` | — | `tidy_directory` | 0.91 | — |" in summary


def test_a_finding_acknowledged_in_the_log_no_longer_fails_the_check(
    repository: Path, tmp_path: Path, capsys: Capture
) -> None:
    judge = FakeJudge(rule_id_to_answer={"short": "fail"}, confidence=0.91)
    audit_diff(judge, tmp_path, tmp_path / "change.diff", capsys)
    report(tmp_path)
    [finding] = read_findings(tmp_path)["findings"]
    command = finding["acknowledge_command"].split()
    # The commit gate logs the same finding under the same ID.
    run_gate(judge)
    assert command[1] in run_git(repository, "status", "--porcelain")

    acknowledged = run_ack(command[1], "--note", "the sum is short enough")
    audit_diff(judge, tmp_path, tmp_path / "change.diff", capsys)
    exit_code = report(tmp_path)

    assert acknowledged == ExitCode.NO_PROBLEMS
    assert exit_code == ExitCode.NO_PROBLEMS
    assert read_findings(tmp_path)["findings"] == []
    assert "klint: no problem found in the" in capsys.readouterr().out


@pytest.mark.usefixtures("repository")
def test_a_pull_request_with_no_change_klint_audits_passes_with_one_line(
    tmp_path: Path, capsys: Capture
) -> None:
    empty_diff = tmp_path / "empty.diff"
    empty_diff.write_text("", encoding="utf-8")
    audit_diff(FakeJudge(default="fail"), tmp_path, empty_diff, capsys)

    exit_code = report(tmp_path)

    assert exit_code == ExitCode.NO_PROBLEMS
    assert capsys.readouterr().out == (
        "klint: no change in this pull request that klint audits.\n"
    )


@pytest.mark.usefixtures("repository")
def test_a_report_that_cannot_be_read_cannot_run(
    tmp_path: Path, capsys: Capture
) -> None:
    (tmp_path / "file.json").write_text("[klint] Error: no judge\n", encoding="utf-8")
    (tmp_path / "structure.json").write_text("{}", encoding="utf-8")

    exit_code = report(tmp_path)

    assert exit_code == ExitCode.RUN_ERROR
    assert "cannot read the report" in capsys.readouterr().err
    assert not (tmp_path / "findings.json").exists()
