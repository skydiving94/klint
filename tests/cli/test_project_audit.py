"""The klint-project command end to end, with the fake judge in place of the model."""

import asyncio
from pathlib import Path

import pytest

from src.app.wiring import create_project_audit_path
from src.cli.project_audit import ProjectAuditCLIApp
from src.core.interfaces.judge import BaseJudge
from tests.support.builders import make_settings
from tests.support.fakes import FakeJudge, JudgeOverride
from tests.support.paths import MOCK_PROJECT, SnapshotAsserter

EXAMPLE_FILE = "examples/backend_data_and_security.py"


Capture = pytest.CaptureFixture[str]


def _project_app(judge: BaseJudge) -> ProjectAuditCLIApp:
    audit_path = create_project_audit_path(make_settings(), JudgeOverride(judge))
    return ProjectAuditCLIApp(audit_path=audit_path)


def _run(app: ProjectAuditCLIApp, *argv: str | Path) -> int:
    return asyncio.run(app.run([str(arg) for arg in argv]))


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
