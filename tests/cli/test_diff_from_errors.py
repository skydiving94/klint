"""The klint command on a diff it cannot trust or read, with --diff-from."""

import io
import json
import sys
from pathlib import Path

import pytest

from klint.cli import ExitCode, run_file_audit
from tests.support.builders import list_lines_before_judge_usage
from tests.support.cart_project import (
    CART_AFTER,
    build_cart_settings,
    create_cart_repository,
    run_file_command,
)
from tests.support.fakes import FakeJudge
from tests.support.git_repository import run_git, write_files

Capture = pytest.CaptureFixture[str]


@pytest.fixture
def repository(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    return create_cart_repository(monkeypatch, tmp_path)


def pipe_to_stdin(monkeypatch: pytest.MonkeyPatch, text: str) -> None:
    """Make ``text`` what the command reads on stdin."""
    stdin = io.TextIOWrapper(io.BytesIO(text.encode("utf-8")), encoding="utf-8")
    monkeypatch.setattr(sys, "stdin", stdin)


def run_on_stdin(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, judge: FakeJudge, diff: str
) -> ExitCode:
    pipe_to_stdin(monkeypatch, diff)
    return run_file_command(
        judge, build_cart_settings(tmp_path), "--diff-from", "-", "--json"
    )


def test_a_file_on_disk_unlike_the_diff_is_refused_by_name(
    repository: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: Capture,
) -> None:
    write_files(repository, {"cart.py": CART_AFTER})
    diff = run_git(repository, "diff")
    # The file moves on after the diff was taken.
    write_files(repository, {"cart.py": CART_AFTER + "\nMORE = 1\n"})
    judge = FakeJudge()

    exit_code = run_on_stdin(monkeypatch, tmp_path, judge, diff)

    (error_line,) = capsys.readouterr().err.splitlines()
    assert exit_code == ExitCode.RUN_ERROR
    assert error_line.startswith(
        "[klint] Error: The diff does not match the files on disk, so its "
        "changed lines cannot be found in them: 'cart.py' hashes to "
    )
    assert judge.requests == []


def test_a_file_the_diff_changes_that_is_not_on_disk_is_refused(
    repository: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: Capture,
) -> None:
    write_files(repository, {"cart.py": CART_AFTER})
    diff = run_git(repository, "diff")
    (repository / "cart.py").unlink()

    exit_code = run_on_stdin(monkeypatch, tmp_path, FakeJudge(), diff)

    assert exit_code == ExitCode.RUN_ERROR
    assert "'cart.py' is not on disk" in capsys.readouterr().err


def test_a_diff_with_no_index_lines_is_taken_as_is_with_one_warning(
    repository: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: Capture,
) -> None:
    write_files(repository, {"cart.py": CART_AFTER})
    diff = "\n".join(
        line
        for line in run_git(repository, "diff").split("\n")
        if not line.startswith("index ")
    )

    exit_code = run_on_stdin(monkeypatch, tmp_path, FakeJudge(), diff)

    captured = capsys.readouterr()
    assert exit_code == ExitCode.NO_PROBLEMS
    assert json.loads(captured.out)["examined_files"] == [
        "cart.py",
        "cart.py::Cart",
        "cart.py::Cart.total",
    ]
    assert list_lines_before_judge_usage(captured.err) == [
        "[klint] Warning: the diff has no index lines, so the files on disk are "
        "taken as the ones it changes, unchecked",
        "[klint] Change in the diff: 1 file, 3 of 5 units selected "
        "(--diff-units units)",
    ]


@pytest.mark.usefixtures("repository")
def test_an_empty_diff_says_so_and_exits_without_a_problem(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: Capture,
) -> None:
    judge = FakeJudge()

    exit_code = run_on_stdin(monkeypatch, tmp_path, judge, "")

    captured = capsys.readouterr()
    assert exit_code == ExitCode.NO_PROBLEMS
    assert list_lines_before_judge_usage(captured.err) == [
        "[klint] No change in the diff to audit",
        "[klint] Change in the diff: 0 files, 0 of 0 units selected "
        "(--diff-units units)",
    ]
    assert json.loads(captured.out)["diff_change"]["files"] == []
    assert judge.requests == []


@pytest.mark.parametrize(
    ("diff", "expected_error"),
    [
        (
            "--- cart.py\n+++ cart.py\n@@ -1 +1 @@\n-a\n+b\n",
            "[klint] Error: Cannot read the diff: line 1: the line '--- cart.py' "
            "is outside any file",
        ),
        (
            "diff --git a/cart.py b/cart.py\n@@ -1,2 +1,2 @@\n-import json\n",
            "[klint] Error: Cannot read the diff: line 2: the hunk "
            "'@@ -1,2 +1,2 @@' ends early",
        ),
        (
            "diff --cc cart.py\nindex 1,2..3\n@@@ -1 -1 +1 @@@\n",
            "[klint] Error: Cannot read the diff: line 1: it is a combined diff, "
            "as git writes for a merge, and only a diff against one side can be "
            "audited",
        ),
    ],
    ids=["not-git-format", "short-hunk", "combined"],
)
@pytest.mark.usefixtures("repository")
def test_a_diff_that_cannot_be_read_stops_naming_the_line(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: Capture,
    diff: str,
    expected_error: str,
) -> None:
    judge = FakeJudge()

    exit_code = run_on_stdin(monkeypatch, tmp_path, judge, diff)

    assert exit_code == ExitCode.RUN_ERROR
    assert capsys.readouterr().err.splitlines() == [expected_error]
    assert judge.requests == []


def test_a_diff_of_a_file_outside_the_current_directory_is_refused(
    repository: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: Capture,
) -> None:
    write_files(repository, {"cart.py": CART_AFTER})
    diff = run_git(repository, "diff")
    subdirectory = repository / "docs"
    subdirectory.mkdir()
    monkeypatch.chdir(subdirectory)

    exit_code = run_on_stdin(
        monkeypatch, tmp_path, FakeJudge(), diff.replace("cart.py", "../cart.py")
    )

    assert exit_code == ExitCode.RUN_ERROR
    assert capsys.readouterr().err.splitlines() == [
        "[klint] Error: The diff changes '../cart.py', which is outside the current "
        f"directory '{subdirectory.resolve()}'"
    ]


@pytest.mark.usefixtures("repository")
def test_a_diff_file_that_cannot_be_read_stops_the_command(
    tmp_path: Path, capsys: Capture
) -> None:
    missing = tmp_path / "missing.diff"

    exit_code = run_file_command(
        FakeJudge(), build_cart_settings(tmp_path), "--diff-from", str(missing)
    )

    assert exit_code == ExitCode.RUN_ERROR
    assert capsys.readouterr().err.splitlines() == [
        f"[klint] Error: Cannot read the diff '{missing}': No such file or directory"
    ]


@pytest.mark.parametrize(
    "argv",
    [
        ["klint", "--diff-from", "-", "cart.py"],
        ["klint", "--diff-from", "-", "--diff"],
        ["klint", "--diff-from"],
    ],
)
def test_a_diff_from_command_line_that_does_not_fit_exits_with_status_2(
    monkeypatch: pytest.MonkeyPatch, argv: list[str]
) -> None:
    monkeypatch.setattr(sys, "argv", argv)

    with pytest.raises(SystemExit) as stopped:
        run_file_audit()

    assert stopped.value.code == ExitCode.RUN_ERROR
