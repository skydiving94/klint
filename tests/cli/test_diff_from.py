"""The klint command on a unified diff, with --diff-from and --diff-units."""

import io
import json
import sys
from pathlib import Path
from typing import Any

import pytest

from klint.cli import ExitCode
from tests.support.builders import list_lines_before_judge_usage
from tests.support.cart_project import (
    CART_AFTER,
    CART_BEFORE,
    HELPERS,
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


def read_json(capsys: Capture) -> dict[str, Any]:
    output: dict[str, Any] = json.loads(capsys.readouterr().out)
    return output


def list_selected(change: dict[str, Any]) -> list[tuple[str, str]]:
    return [(unit["unit_id"], unit["unit_type"]) for unit in change["selected_units"]]


def test_a_piped_diff_selects_the_units_the_staged_change_would(
    repository: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: Capture,
) -> None:
    write_files(repository, {"cart.py": CART_AFTER})
    run_git(repository, "add", "cart.py")
    settings = build_cart_settings(tmp_path)
    run_file_command(FakeJudge(), settings, "--diff", "--json")
    staged_output = read_json(capsys)
    # A plain git diff, with three lines of context around each change.
    pipe_to_stdin(monkeypatch, run_git(repository, "diff", "--cached"))
    judge = FakeJudge()

    exit_code = run_file_command(judge, settings, "--diff-from", "-", "--json")

    output = read_json(capsys)
    assert exit_code == ExitCode.NO_PROBLEMS
    assert output["examined_files"] == [
        "cart.py",
        "cart.py::Cart",
        "cart.py::Cart.total",
    ]
    assert output["diff_change"] == staged_output["staged_change"]
    assert "staged_change" not in output
    assert len(judge.requests) == 3


def test_a_diff_in_a_file_is_reported_as_the_change_in_the_diff(
    repository: Path, tmp_path: Path, capsys: Capture
) -> None:
    write_files(repository, {"cart.py": CART_AFTER})
    diff_path = tmp_path / "change.diff"
    diff_path.write_text(run_git(repository, "diff"), encoding="utf-8")

    exit_code = run_file_command(
        FakeJudge(), build_cart_settings(tmp_path), "--diff-from", str(diff_path)
    )

    captured = capsys.readouterr()
    assert exit_code == ExitCode.NO_PROBLEMS
    assert "1 files scanned, 3 units audited" in captured.out
    assert list_lines_before_judge_usage(captured.err) == [
        "[klint] Change in the diff: 1 file, 3 of 5 units selected (--diff-units units)"
    ]


@pytest.mark.parametrize(
    ("diff_units", "expected_units"),
    [
        ("units", [("cart.py", "file"), ("cart.py::Cart", "class")]),
        ("file", [("cart.py", "file")]),
        (
            "all",
            [
                ("cart.py", "file"),
                ("cart.py::Cart", "class"),
                ("cart.py::Cart.add", "function"),
                ("cart.py::Cart.total", "function"),
                ("cart.py::load", "function"),
            ],
        ),
    ],
)
def test_diff_units_choose_among_the_units_of_the_changed_files(
    repository: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: Capture,
    diff_units: str,
    expected_units: list[tuple[str, str]],
) -> None:
    # The class's docstring changes: no method is on a changed line.
    write_files(
        repository,
        {"cart.py": CART_BEFORE.replace("A shopping cart.", "A cart of items.")},
    )
    run_git(repository, "add", "cart.py")
    run_git(repository, "commit", "--quiet", "--message", "Changing the cart")
    pipe_to_stdin(monkeypatch, run_git(repository, "diff", "HEAD~1", "HEAD"))
    # The working tree holds the commit's files, the ones the diff names.

    run_file_command(
        FakeJudge(),
        build_cart_settings(tmp_path),
        "--diff-from",
        "-",
        "--diff-units",
        diff_units,
        "--json",
    )

    output = read_json(capsys)
    assert list_selected(output["diff_change"]) == expected_units
    assert output["diff_change"]["diff_units"] == diff_units


def test_an_added_file_is_changed_on_every_line_and_a_deleted_one_is_skipped(
    repository: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: Capture,
) -> None:
    price_module = "def price(item: str) -> int:\n    return 1\n"
    write_files(repository, {"pricing.py": price_module})
    run_git(repository, "rm", "--quiet", "helpers.py")
    run_git(repository, "add", "pricing.py")
    pipe_to_stdin(monkeypatch, run_git(repository, "diff", "--cached"))

    run_file_command(
        FakeJudge(), build_cart_settings(tmp_path), "--diff-from", "-", "--json"
    )

    output = read_json(capsys)
    assert output["examined_files"] == ["pricing.py", "pricing.py::price"]
    assert output["diff_change"]["files"] == ["pricing.py"]
    assert output["diff_change"]["deleted_files"] == ["helpers.py"]


def test_a_rename_is_audited_under_its_new_path(
    repository: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: Capture,
) -> None:
    run_git(repository, "mv", "helpers.py", "text_helpers.py")
    write_files(repository, {"text_helpers.py": HELPERS.replace("upper", "lower")})
    run_git(repository, "add", "text_helpers.py")
    pipe_to_stdin(monkeypatch, run_git(repository, "diff", "--cached", "-M"))

    run_file_command(
        FakeJudge(), build_cart_settings(tmp_path), "--diff-from", "-", "--json"
    )

    output = read_json(capsys)
    assert output["examined_files"] == ["text_helpers.py", "text_helpers.py::shout"]
    assert output["diff_change"]["files"] == ["text_helpers.py"]


@pytest.mark.parametrize(
    ("diff_units", "expected_units"),
    [
        ("units", ["text_helpers.py"]),
        ("file", ["text_helpers.py"]),
        ("all", ["text_helpers.py", "text_helpers.py::shout"]),
    ],
)
def test_a_rename_with_no_edits_gets_its_file_unit_alone_but_with_all(
    repository: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: Capture,
    diff_units: str,
    expected_units: list[str],
) -> None:
    run_git(repository, "mv", "helpers.py", "text_helpers.py")
    pipe_to_stdin(monkeypatch, run_git(repository, "diff", "--cached", "-M"))

    run_file_command(
        FakeJudge(),
        build_cart_settings(tmp_path),
        "--diff-from",
        "-",
        "--diff-units",
        diff_units,
        "--json",
    )

    assert read_json(capsys)["examined_files"] == expected_units


def test_a_diff_with_no_prefix_and_a_path_with_spaces_is_read(
    repository: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: Capture,
) -> None:
    write_files(repository, {"price list.py": "def list_prices() -> None:\n    pass\n"})
    run_git(repository, "add", "price list.py")
    run_git(repository, "commit", "--quiet", "--message", "Adding the prices")
    write_files(
        repository, {"price list.py": "def list_prices() -> None:\n    return None\n"}
    )
    pipe_to_stdin(monkeypatch, run_git(repository, "diff", "--no-prefix"))

    run_file_command(
        FakeJudge(), build_cart_settings(tmp_path), "--diff-from", "-", "--json"
    )

    output = read_json(capsys)
    assert output["examined_files"] == [
        "price list.py",
        "price list.py::list_prices",
    ]


@pytest.mark.parametrize("diff_units", ["units", "file", "all"])
def test_a_binary_file_is_listed_but_has_no_unit_to_audit(
    repository: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: Capture,
    diff_units: str,
) -> None:
    # As in an audit of a path, a binary file gives no unit, its file's neither.
    write_files(repository, {"logo.png": b"\x89PNG\r\n\x1a\n\x00\x01\x02"})
    run_git(repository, "add", "logo.png")
    pipe_to_stdin(monkeypatch, run_git(repository, "diff", "--cached"))
    judge = FakeJudge()

    exit_code = run_file_command(
        judge,
        build_cart_settings(tmp_path),
        "--diff-from",
        "-",
        "--diff-units",
        diff_units,
        "--json",
    )

    output = read_json(capsys)
    assert exit_code == ExitCode.NO_PROBLEMS
    assert output["diff_change"]["files"] == ["logo.png"]
    assert output["examined_files"] == []
    assert judge.requests == []
