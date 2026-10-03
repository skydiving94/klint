"""Both CLI commands end to end, with the fake judge in place of the model."""

import asyncio
import json
from pathlib import Path
from typing import Any
from unittest.mock import Mock

import pytest

from src.app.wiring import create_file_audit_path, create_project_audit_path
from src.cli.basic_audit import CLIApp
from src.cli.project_audit import ProjectAuditCLIApp
from src.core.interfaces.judge import BaseJudge
from src.infra.system_one.remote import RemoteSystemOneJudge
from tests.helpers import (
    FILE_RULE,
    FakeJudge,
    JudgeOverride,
    SnapshotAsserter,
    make_settings,
    write_json,
)

EXAMPLE_FILE = "examples/backend_data_and_security.py"
MOCK_PROJECT = "examples/mock_bad_project"

Capture = pytest.CaptureFixture[str]


def _file_app(judge: BaseJudge) -> CLIApp:
    audit_path = create_file_audit_path(make_settings(), JudgeOverride(judge))
    return CLIApp(audit_path=audit_path)


def _project_app(judge: BaseJudge) -> ProjectAuditCLIApp:
    audit_path = create_project_audit_path(make_settings(), JudgeOverride(judge))
    return ProjectAuditCLIApp(audit_path=audit_path)


def _run(app: CLIApp | ProjectAuditCLIApp, *argv: str | Path) -> int:
    return asyncio.run(app.run([str(arg) for arg in argv]))


def _json_output(capsys: Capture) -> dict[str, Any]:
    output: dict[str, Any] = json.loads(capsys.readouterr().out)
    return output


# --- klint: file audit -----------------------------------------------------


@pytest.mark.usefixtures("in_repo_root")
def test_file_audit_json_matches_snapshot(
    fake_judge: type[FakeJudge], capsys: Capture, assert_snapshot: SnapshotAsserter
) -> None:
    judge = fake_judge(choices={"hardcoded_secrets": "fail", "n_plus_1_query": "fail"})

    exit_code = _run(_file_app(judge), EXAMPLE_FILE, "--json")

    assert exit_code == 0  # failures do not change the exit code today
    assert_snapshot("cli_file_audit.json", capsys.readouterr().out)


@pytest.mark.usefixtures("in_repo_root")
def test_all_flag_reports_every_judgment(
    fake_judge: type[FakeJudge], capsys: Capture
) -> None:
    judge = fake_judge(choices={"hardcoded_secrets": "fail"})

    _run(_file_app(judge), EXAMPLE_FILE, "--json", "--all")

    judgments = [issue["judgment"] for issue in _json_output(capsys)["issues"]]
    assert judgments == ["Fail"] + ["Pass"] * 15


@pytest.mark.usefixtures("in_repo_root")
def test_min_confidence_hides_low_confidence_findings(
    fake_judge: type[FakeJudge], capsys: Capture
) -> None:
    judge = fake_judge(default="fail", confidence=0.4)

    _run(_file_app(judge), EXAMPLE_FILE, "--json", "--min-confidence", "0.5")

    assert _json_output(capsys) == {"examined_files": [EXAMPLE_FILE], "issues": []}


def test_directory_audit_skips_ignored_and_binary_files(
    tmp_path: Path, fake_judge: type[FakeJudge], capsys: Capture
) -> None:
    (tmp_path / "node_modules").mkdir()
    for name in ("b.tsx", "a.py", "logo.png", ".env", "node_modules/dep.js"):
        (tmp_path / name).write_text("x\n", encoding="utf-8")
    (tmp_path / "blob.dat").write_bytes(b"\x00\x01")
    judge = fake_judge()

    _run(_file_app(judge), tmp_path, "--json")

    examined = _json_output(capsys)["examined_files"]
    assert examined == [str(tmp_path / "a.py"), str(tmp_path / "b.tsx")]
    assert len(judge.calls) == 2


@pytest.mark.usefixtures("in_repo_root")
def test_rules_flag_adds_custom_rules_to_the_defaults(
    tmp_path: Path, fake_judge: type[FakeJudge], capsys: Capture
) -> None:
    custom = write_json(tmp_path / "custom.json", {"house_rule": FILE_RULE})
    judge = fake_judge(choices={"house_rule": "fail"})

    _run(_file_app(judge), EXAMPLE_FILE, "--json", "--rules", custom)

    assert [i["rule_id"] for i in _json_output(capsys)["issues"]] == ["house_rule"]
    assert len(judge.asked_rule_ids()[0]) == 17


def test_missing_target_or_rules_file_exits_with_an_error(
    tmp_path: Path, fake_judge: type[FakeJudge], capsys: Capture
) -> None:
    app = _file_app(fake_judge())
    target = tmp_path / "a.py"
    target.write_text("x = 1\n", encoding="utf-8")

    assert _run(app, tmp_path / "absent.py") == 1
    assert "Audit target does not exist" in capsys.readouterr().err
    assert _run(app, target, "--rules", tmp_path / "absent.json") == 1
    assert "Custom rules file does not exist" in capsys.readouterr().err


def test_file_the_judge_fails_on_is_skipped(tmp_path: Path, capsys: Capture) -> None:
    target = tmp_path / "a.py"
    target.write_text("x = 1\n", encoding="utf-8")
    broken_judge = Mock(side_effect=RuntimeError("judge is down"))
    judge = RemoteSystemOneJudge(model_name="fake", inference_fn=broken_judge)

    exit_code = _run(_file_app(judge), target, "--json")

    captured = capsys.readouterr()
    assert exit_code == 0
    assert json.loads(captured.out) == {"examined_files": [], "issues": []}
    assert f"Skipping {target}: judge is down" in captured.err


@pytest.mark.usefixtures("in_repo_root")
def test_terminal_report_shows_findings_and_summary(
    fake_judge: type[FakeJudge], capsys: Capture
) -> None:
    _run(_file_app(fake_judge()), EXAMPLE_FILE)
    assert "No architectural or semantic issues found." in capsys.readouterr().out

    judge = fake_judge(choices={"hardcoded_secrets": "fail"})
    _run(_file_app(judge), EXAMPLE_FILE)

    report = capsys.readouterr().out
    assert "klint Audit Report" in report
    assert "[FAIL]" in report
    assert "hardcoded_secrets" in report
    assert "(lines 1-43)" in report
    assert "1 files examined" in report
    assert "1 failure(s)" in report


# --- klint-project: project audit ------------------------------------------


@pytest.mark.usefixtures("in_repo_root")
def test_project_audit_json_matches_snapshot(
    fake_judge: type[FakeJudge], capsys: Capture, assert_snapshot: SnapshotAsserter
) -> None:
    judge = fake_judge(choices={"circular_package_dependencies": "fail"})

    exit_code = _run(_project_app(judge), MOCK_PROJECT, "--json")

    assert exit_code == 0
    assert_snapshot("cli_project_audit.json", capsys.readouterr().out)
    # One judge call per directory: the root and its three subdirectories.
    assert [len(rule_ids) for rule_ids in judge.asked_rule_ids()] == [18] * 4


@pytest.mark.usefixtures("in_repo_root")
def test_project_audit_rejects_a_file_target(
    fake_judge: type[FakeJudge], capsys: Capture
) -> None:
    exit_code = _run(_project_app(fake_judge()), EXAMPLE_FILE)

    assert exit_code == 1
    assert "must be a directory" in capsys.readouterr().err
