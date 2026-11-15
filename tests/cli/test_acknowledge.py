"""klint-ack: what it refuses, and how it reports."""

from pathlib import Path

import pytest

from klint.cli import ExitCode
from tests.support.fakes import FakeJudge
from tests.support.git_repository import isolate_git
from tests.support.pre_commit import (
    CART_AFTER,
    LOG_FOLDER,
    read_entries,
    run_ack,
    run_gate,
    set_up_gate_repository,
    stage,
)

Capture = pytest.CaptureFixture[str]


@pytest.fixture
def repository_with_open_entry(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, shell_env: dict[str, str]
) -> Path:
    """Return a repository, as the cwd, whose log holds one open entry."""
    del shell_env
    isolate_git(monkeypatch, tmp_path)
    repository = set_up_gate_repository(monkeypatch, tmp_path)
    stage(repository, {"cart.py": CART_AFTER})
    run_gate(FakeJudge(rule_id_to_answer={"short": "fail"}))
    return repository


def _read_error(capsys: Capture) -> str:
    return capsys.readouterr().err.splitlines()[-1]


def test_an_unknown_id_is_refused_naming_the_log(
    repository_with_open_entry: Path, capsys: Capture
) -> None:
    exit_code = run_ack("000000000000", "--note", "a note")

    assert exit_code == ExitCode.RUN_ERROR
    assert _read_error(capsys) == (
        "[klint-ack] Error: there is no entry '000000000000' in "
        f"{repository_with_open_entry / LOG_FOLDER}; the IDs are those "
        "klint-pre-commit prints"
    )


def test_an_entry_is_acknowledged_once(
    repository_with_open_entry: Path, capsys: Capture
) -> None:
    [entry] = read_entries(repository_with_open_entry)
    run_ack(entry["id"], "--note", "first note")

    exit_code = run_ack(entry["id"], "--note", "second note")

    assert exit_code == ExitCode.RUN_ERROR
    assert _read_error(capsys) == (
        f"[klint-ack] Error: entry '{entry['id']}' is already acknowledged: first note"
    )
    assert read_entries(repository_with_open_entry)[0]["note"] == "first note"


def test_the_note_is_required_and_must_say_something(
    repository_with_open_entry: Path, capsys: Capture
) -> None:
    [entry] = read_entries(repository_with_open_entry)

    with pytest.raises(SystemExit):
        run_ack(entry["id"])
    exit_code = run_ack(entry["id"], "--note", "   ")

    assert exit_code == ExitCode.RUN_ERROR
    assert _read_error(capsys) == (
        "[klint-ack] Error: the note must say why the finding is wrong"
    )
    assert read_entries(repository_with_open_entry)[0]["status"] == "open"


def test_a_malformed_entry_file_is_reported_with_its_path(
    repository_with_open_entry: Path, capsys: Capture
) -> None:
    path = repository_with_open_entry / LOG_FOLDER / "abcdefabcdef.json"
    path.write_text("not json", encoding="utf-8")

    exit_code = run_ack("abcdefabcdef", "--note", "a note")

    assert exit_code == ExitCode.RUN_ERROR
    assert _read_error(capsys).startswith(
        f"[klint-ack] Error: The acknowledgement log entry '{path}' cannot be "
        "read: not valid JSON"
    )


def test_outside_a_git_repository_the_command_stops(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: Capture
) -> None:
    isolate_git(monkeypatch, tmp_path)
    outside = tmp_path / "outside"
    outside.mkdir()
    monkeypatch.chdir(outside)

    exit_code = run_ack("abcdefabcdef", "--note", "a note")

    assert exit_code == ExitCode.RUN_ERROR
    assert _read_error(capsys) == (
        f"[klint-ack] Error: '{outside}' is not in a git repository"
    )
