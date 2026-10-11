"""The klint-project command end to end, with the fake judge in place of the model."""

import asyncio
import sys
from pathlib import Path

import pytest

from src.app.settings import AppSettings
from src.app.wiring import create_project_audit_path
from src.cli.project_audit import ProjectAuditCLIApp, main
from src.core.interfaces.judge import BaseJudge
from tests.support.builders import make_settings, write_text
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


def _run_main(
    monkeypatch: pytest.MonkeyPatch, settings: AppSettings, target: Path
) -> int:
    """Run the command as the shell would, but with the given settings."""
    monkeypatch.setattr(AppSettings, "from_env", lambda *_args: settings)
    monkeypatch.setattr(sys, "argv", ["klint-project", str(target)])
    return asyncio.run(main())


def test_unusable_language_to_file_extensions_file_stops_the_command(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: Capture
) -> None:
    broken = write_text(tmp_path / "language_to_file_extensions.json", "{not json")
    settings = make_settings(language_to_file_extensions_path=broken)

    exit_code = _run_main(monkeypatch, settings, tmp_path)

    captured = capsys.readouterr()
    assert exit_code == 1
    assert captured.out == ""
    assert captured.err.startswith(
        "[klint-project] Error: Language-to-file-extensions file"
    )
    assert str(broken) in captured.err
    assert captured.err.count("\n") == 1


def test_missing_project_rule_packs_stop_the_command_with_one_line(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: Capture
) -> None:
    settings = make_settings(project_rules_paths=())

    exit_code = _run_main(monkeypatch, settings, tmp_path)

    captured = capsys.readouterr()
    assert exit_code == 1
    assert captured.err.startswith("[klint-project] Error: ")
    assert "KEV_DEFAULT_PROJECT_RULES_PATH" in captured.err
    assert captured.err.count("\n") == 1
