"""The confidence a finding needs to block a commit: the judge's, the project's."""

from pathlib import Path

import pytest

from klint.cli import ExitCode
from tests.support.builders import write_json
from tests.support.fakes import FakeJudge
from tests.support.git_repository import isolate_git
from tests.support.pre_commit import (
    CART_AFTER,
    read_entries,
    run_gate,
    set_up_gate_repository,
    stage,
)


def _set_up(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, model_name: str) -> Path:
    isolate_git(monkeypatch, tmp_path)
    repository = set_up_gate_repository(monkeypatch, tmp_path, model_name)
    stage(repository, {"cart.py": CART_AFTER})
    return repository


def _build_judge(confidence: float) -> FakeJudge:
    return FakeJudge(rule_id_to_answer={"short": "fail"}, confidence=confidence)


@pytest.mark.usefixtures("shell_env")
@pytest.mark.parametrize(
    ("model_name", "confidence", "expected"),
    [
        ("jev-latest", 0.79, ExitCode.NO_PROBLEMS),
        ("jev-latest", 0.8, ExitCode.PROBLEMS_FOUND),
        ("jaredpalmer/kev-4b", 0.49, ExitCode.NO_PROBLEMS),
        ("jaredpalmer/kev-4b", 0.5, ExitCode.PROBLEMS_FOUND),
        ("jaredpalmer/kev-9b", 0.5, ExitCode.PROBLEMS_FOUND),
        ("some-other-model", 0.79, ExitCode.NO_PROBLEMS),
    ],
)
def test_the_default_threshold_comes_from_the_judge_in_use(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    model_name: str,
    confidence: float,
    expected: ExitCode,
) -> None:
    _set_up(monkeypatch, tmp_path, model_name)

    assert run_gate(_build_judge(confidence)) == expected


@pytest.mark.usefixtures("shell_env")
def test_the_projects_klint_json_sets_its_own_threshold(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    repository = _set_up(monkeypatch, tmp_path, "jev-latest")
    write_json(
        repository / "klint.json", {"env": {"KLINT_COMMIT_MIN_CONFIDENCE": "0.6"}}
    )

    assert run_gate(_build_judge(0.6)) == ExitCode.PROBLEMS_FOUND
    assert read_entries(repository)[0]["finding"]["confidence"] == 0.6


@pytest.mark.usefixtures("shell_env")
def test_the_command_line_threshold_wins(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    repository = _set_up(monkeypatch, tmp_path, "jev-latest")
    write_json(
        repository / "klint.json", {"env": {"KLINT_COMMIT_MIN_CONFIDENCE": "0.6"}}
    )

    assert (
        run_gate(_build_judge(0.6), "--min-confidence", "0.7") == ExitCode.NO_PROBLEMS
    )


@pytest.mark.usefixtures("shell_env")
def test_a_threshold_setting_that_is_not_a_number_stops_the_command(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _set_up(monkeypatch, tmp_path, "jev-latest")
    monkeypatch.setenv("KLINT_COMMIT_MIN_CONFIDENCE", "high")

    exit_code = run_gate(_build_judge(0.9))

    assert exit_code == ExitCode.RUN_ERROR
    assert capsys.readouterr().err.splitlines()[-1] == (
        "[klint-pre-commit] Error: KLINT_COMMIT_MIN_CONFIDENCE 'high' set in the "
        "environment must be a number from 0.0 to 1.0"
    )
