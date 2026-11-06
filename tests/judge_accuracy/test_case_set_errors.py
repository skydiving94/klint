"""Case sets the scoring command cannot score, and how it says so."""

from pathlib import Path

import pytest

from judge_accuracy.change_summary.scoring_command import ScoringExitCode
from tests.judge_accuracy.scoring import (
    FALSE_IMPORT_MISTAKE,
    IMPORT_HUNK_POINTER,
    run_scoring_command,
    write_case_file,
)
from tests.support.builders import write_text
from tests.support.change_summary import HypothesisJudge, copy_greeting_document

Capture = pytest.CaptureFixture[str]


@pytest.fixture(autouse=True)
def _private_environment(shell_env: dict[str, str]) -> None:
    del shell_env


def _run_and_read_error(case_set: Path, capsys: Capture) -> str:
    judge = HypothesisJudge()
    exit_code = run_scoring_command(judge, case_set)
    assert exit_code == ScoringExitCode.RUN_ERROR
    assert judge.requests == []
    return capsys.readouterr().err


def test_a_folder_with_no_case_file_ends_with_exit_2(
    tmp_path: Path, capsys: Capture
) -> None:
    error = _run_and_read_error(tmp_path, capsys)

    assert error == f"[judge-accuracy] Error: {tmp_path} holds no case file (*.json)\n"


@pytest.mark.parametrize(
    ("mistake_change", "expected_error"),
    [
        (
            {"summary_pointer": "#/root_package/files/9/summary"},
            "planted_mistakes/0/summary_pointer: #/root_package/files/9/summary "
            "names nothing in the document",
        ),
        (
            {"summary_pointer": "#/root_package/path"},
            "planted_mistakes/0/summary_pointer: #/root_package/path does not "
            "end with /summary",
        ),
        (
            {"summary": "Removes the unused import of os."},
            "planted_mistakes/0/summary is the true summary itself",
        ),
        (
            {"mistake_kind": "typo"},
            "planted_mistakes/0/mistake_kind 'typo' is not one of "
            "['false_statement', 'unsupported_reason', 'contradiction', 'omission']",
        ),
        (
            {"why_wrong": ""},
            "planted_mistakes/0/why_wrong is not a non-empty string",
        ),
    ],
)
def test_a_planted_mistake_that_cannot_be_planted_ends_with_exit_2(
    tmp_path: Path,
    capsys: Capture,
    mistake_change: dict[str, str],
    expected_error: str,
) -> None:
    path = write_case_file(tmp_path, "greeting", FALSE_IMPORT_MISTAKE | mistake_change)

    error = _run_and_read_error(tmp_path, capsys)

    assert error == f"[judge-accuracy] Error: {path}: {expected_error}\n"


def test_the_same_planted_summary_twice_ends_with_exit_2(
    tmp_path: Path, capsys: Capture
) -> None:
    path = write_case_file(
        tmp_path, "greeting", FALSE_IMPORT_MISTAKE, FALSE_IMPORT_MISTAKE
    )

    error = _run_and_read_error(tmp_path, capsys)

    assert error == (
        f"[judge-accuracy] Error: {path}: {IMPORT_HUNK_POINTER} is given the "
        "same planted summary twice\n"
    )


def test_a_case_file_that_is_not_json_ends_with_exit_2(
    tmp_path: Path, capsys: Capture
) -> None:
    path = write_text(tmp_path / "broken.json", "{")

    error = _run_and_read_error(tmp_path, capsys)

    assert error.startswith(f"[judge-accuracy] Error: {path} is not JSON: ")


def test_a_true_document_klint_cannot_read_ends_with_exit_2(
    tmp_path: Path, capsys: Capture
) -> None:
    document = copy_greeting_document()
    document["schema_version"] = 7
    write_case_file(tmp_path, "greeting", true_document=document)

    error = _run_and_read_error(tmp_path, capsys)

    assert error.endswith(
        "[judge-accuracy] Error: greeting: Change-summary document: "
        "#/schema_version is 7; klint reads schema_version 1 only\n"
    )
