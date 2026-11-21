"""The klint command on the staged change, with --diff and --diff-units."""

import asyncio
import json
import sys
from pathlib import Path
from typing import Any

import pytest

from klint.app import AppSettings
from klint.cli import FILE_AUDIT_COMMAND, ExitCode, run_file_audit
from klint.core.interfaces import BaseJudge
from tests.support.builders import (
    build_audit_command_app,
    list_lines_before_judge_usage,
    make_settings,
    write_json,
)
from tests.support.cart_project import (
    ALL_RULES,
    CART_AFTER,
    CART_BEFORE,
    GO_BEFORE,
    HELPERS,
)
from tests.support.fakes import FakeJudge, SubjectJudge
from tests.support.git_repository import (
    create_repository,
    isolate_git,
    run_git,
    write_files,
)

Capture = pytest.CaptureFixture[str]


@pytest.fixture
def repository(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    """Return a repository holding a cart module, a Go file and a helper, as the cwd."""
    isolate_git(monkeypatch, tmp_path)
    repository = create_repository(
        tmp_path / "shop",
        {"cart.py": CART_BEFORE, "helpers.py": HELPERS, "main.go": GO_BEFORE},
    )
    monkeypatch.chdir(repository)
    return repository


def _stage(repository: Path, path_to_content: dict[str, str]) -> None:
    """Write each file and stage it."""
    write_files(repository, path_to_content)
    run_git(repository, "add", "--", *path_to_content)


def _build_settings(tmp_path: Path, **rules: dict[str, Any]) -> AppSettings:
    """Return settings whose one built-in pack holds ``rules``, or every rule."""
    pack = write_json(tmp_path / "rules.json", rules or ALL_RULES)
    return make_settings(built_in_rule_packs=[pack], fallback_rule_packs=[pack])


def _run(judge: BaseJudge, settings: AppSettings, *options: str) -> ExitCode:
    app = build_audit_command_app(FILE_AUDIT_COMMAND, judge, settings)
    return asyncio.run(app.run(list(options)))


def _read_json(capsys: Capture) -> dict[str, Any]:
    output: dict[str, Any] = json.loads(capsys.readouterr().out)
    return output


def _list_selected(staged_change: dict[str, Any]) -> list[tuple[str, str]]:
    return [
        (unit["unit_id"], unit["unit_type"]) for unit in staged_change["selected_units"]
    ]


def test_diff_audits_the_file_unit_and_the_units_on_the_changed_lines(
    repository: Path, tmp_path: Path, capsys: Capture
) -> None:
    _stage(repository, {"cart.py": CART_AFTER})
    judge = FakeJudge()

    exit_code = _run(judge, _build_settings(tmp_path), "--diff", "--json")

    output = _read_json(capsys)
    assert exit_code == ExitCode.NO_PROBLEMS
    # The file, the class the changed method is in, and the method: not the
    # other method, nor the function on unchanged lines.
    assert output["examined_files"] == [
        "cart.py",
        "cart.py::Cart",
        "cart.py::Cart.total",
    ]
    assert output["staged_change"] == {
        "diff_units": "units",
        "files": ["cart.py"],
        "deleted_files": [],
        "unit_count": 5,
        "selected_unit_count": 3,
        "selected_units": [
            {
                "unit_id": "cart.py",
                "unit_type": "file",
                "location": {"path": "cart.py", "start_line": 1, "end_line": 17},
                "context": {},
            },
            {
                "unit_id": "cart.py::Cart",
                "unit_type": "class",
                "location": {"path": "cart.py", "start_line": 4, "end_line": 13},
                "context": {"qualified_name": "Cart"},
            },
            {
                "unit_id": "cart.py::Cart.total",
                "unit_type": "function",
                "location": {"path": "cart.py", "start_line": 10, "end_line": 13},
                "context": {"qualified_name": "Cart.total"},
            },
        ],
    }
    assert len(judge.requests) == 3


def test_the_terminal_report_counts_the_selected_units(
    repository: Path, tmp_path: Path, capsys: Capture
) -> None:
    _stage(repository, {"cart.py": CART_AFTER})

    _run(FakeJudge(), _build_settings(tmp_path), "--diff")

    captured = capsys.readouterr()
    assert "1 files scanned, 3 units audited" in captured.out
    assert list_lines_before_judge_usage(captured.err) == [
        "[klint] Staged change: 1 file, 3 of 5 units selected (--diff-units units)"
    ]


def test_diff_units_file_audits_the_file_units_only(
    repository: Path, tmp_path: Path, capsys: Capture
) -> None:
    _stage(repository, {"cart.py": CART_AFTER, "helpers.py": HELPERS + "\n"})
    judge = FakeJudge()

    _run(judge, _build_settings(tmp_path), "--diff", "--diff-units", "file", "--json")

    output = _read_json(capsys)
    assert output["examined_files"] == ["cart.py", "helpers.py"]
    assert _list_selected(output["staged_change"]) == [
        ("cart.py", "file"),
        ("helpers.py", "file"),
    ]
    assert (
        output["staged_change"]["unit_count"],
        output["staged_change"]["selected_unit_count"],
    ) == (7, 2)
    assert len(judge.requests) == 2


def test_diff_units_all_audits_every_unit_of_the_changed_files(
    repository: Path, tmp_path: Path, capsys: Capture
) -> None:
    _stage(repository, {"cart.py": CART_AFTER})
    judge = FakeJudge()

    _run(judge, _build_settings(tmp_path), "--diff", "--diff-units", "all", "--json")

    output = _read_json(capsys)
    assert output["examined_files"] == [
        "cart.py",
        "cart.py::Cart",
        "cart.py::Cart.add",
        "cart.py::Cart.total",
        "cart.py::load",
    ]
    assert output["staged_change"]["selected_unit_count"] == 5
    assert len(judge.requests) == 5


def test_a_staged_new_file_counts_as_changed_on_every_line(
    repository: Path, tmp_path: Path, capsys: Capture
) -> None:
    _stage(repository, {"pricing.py": "def price(item: str) -> int:\n    return 1\n"})

    _run(FakeJudge(), _build_settings(tmp_path), "--diff", "--json")

    output = _read_json(capsys)
    assert output["examined_files"] == ["pricing.py", "pricing.py::price"]
    assert output["staged_change"]["files"] == ["pricing.py"]


def test_a_staged_deletion_is_skipped_and_a_pure_deletion_touches_the_units_around_it(
    repository: Path, tmp_path: Path, capsys: Capture
) -> None:
    # The docstring of total goes: a hunk that removes a line and adds none.
    without_docstring = CART_BEFORE.replace(
        '        """Return the sum of the prices."""\n', ""
    )
    _stage(repository, {"cart.py": without_docstring})
    run_git(repository, "rm", "--quiet", "helpers.py")

    _run(FakeJudge(), _build_settings(tmp_path), "--diff", "--json")

    output = _read_json(capsys)
    assert output["examined_files"] == [
        "cart.py",
        "cart.py::Cart",
        "cart.py::Cart.total",
    ]
    assert output["staged_change"]["files"] == ["cart.py"]
    assert output["staged_change"]["deleted_files"] == ["helpers.py"]


def test_a_staged_rename_is_audited_under_its_new_path(
    repository: Path, tmp_path: Path, capsys: Capture
) -> None:
    run_git(repository, "mv", "helpers.py", "text_helpers.py")
    _stage(repository, {"text_helpers.py": HELPERS.replace("upper", "lower")})

    _run(FakeJudge(), _build_settings(tmp_path), "--diff", "--json")

    output = _read_json(capsys)
    assert output["examined_files"] == ["text_helpers.py", "text_helpers.py::shout"]
    assert output["staged_change"]["files"] == ["text_helpers.py"]


def test_a_file_in_a_language_without_an_extractor_gets_its_file_unit(
    repository: Path, tmp_path: Path, capsys: Capture
) -> None:
    _stage(repository, {"main.go": GO_BEFORE.replace("{}", "{\n}")})
    judge = FakeJudge()

    _run(judge, _build_settings(tmp_path), "--diff", "--json")

    output = _read_json(capsys)
    assert output["examined_files"] == ["main.go"]
    assert _list_selected(output["staged_change"]) == [("main.go", "file")]
    assert output["staged_change"]["unit_count"] == 1


def test_findings_on_a_selected_unit_match_those_of_a_full_audit(
    repository: Path, tmp_path: Path, capsys: Capture
) -> None:
    _stage(repository, {"cart.py": CART_AFTER})
    settings = _build_settings(tmp_path)
    judge_for_diff = SubjectJudge({_find_total_source(): "fail"}, confidence=0.7)
    judge_for_full = SubjectJudge({_find_total_source(): "fail"}, confidence=0.7)

    _run(judge_for_diff, settings, "--diff", "--json")
    diff_findings = _read_json(capsys)["findings"]
    _run(judge_for_full, settings, "cart.py", "--json")
    full_findings = _read_json(capsys)["findings"]

    assert diff_findings == full_findings
    assert [finding["unit_id"] for finding in diff_findings] == ["cart.py::Cart.total"]


def _find_total_source() -> str:
    """Return the source of the changed total method, as the judge is shown it."""
    lines = CART_AFTER.splitlines()
    return "\n".join(line[4:] for line in lines[9:13])


def test_nothing_staged_says_so_and_exits_without_a_problem(
    repository: Path, tmp_path: Path, capsys: Capture
) -> None:
    write_files(repository, {"cart.py": CART_AFTER})
    judge = FakeJudge()

    exit_code = _run(judge, _build_settings(tmp_path), "--diff", "--json")

    captured = capsys.readouterr()
    output = json.loads(captured.out)
    assert exit_code == ExitCode.NO_PROBLEMS
    assert list_lines_before_judge_usage(captured.err) == [
        "[klint] No staged change to audit",
        "[klint] Staged change: 0 files, 0 of 0 units selected (--diff-units units)",
    ]
    assert output["examined_files"] == []
    assert output["staged_change"]["files"] == []
    assert judge.requests == []


def test_a_staged_file_with_unstaged_edits_too_is_warned_about(
    repository: Path, tmp_path: Path, capsys: Capture
) -> None:
    _stage(repository, {"cart.py": CART_AFTER})
    write_files(repository, {"cart.py": CART_AFTER + "\n\nMORE = 1\n"})

    _run(FakeJudge(), _build_settings(tmp_path), "--diff", "--json")

    captured = capsys.readouterr()
    assert list_lines_before_judge_usage(captured.err) == [
        "[klint] Warning: 'cart.py' has unstaged edits too: its units are read "
        "from the working tree, and the changed lines from the index",
        "[klint] Staged change: 1 file, 3 of 5 units selected (--diff-units units)",
    ]


def test_outside_a_git_repository_the_command_stops_with_the_reason(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: Capture
) -> None:
    isolate_git(monkeypatch, tmp_path)
    outside = tmp_path / "outside"
    outside.mkdir()
    monkeypatch.chdir(outside)
    judge = FakeJudge()

    exit_code = _run(judge, _build_settings(tmp_path), "--diff")

    (error_line,) = capsys.readouterr().err.splitlines()
    assert exit_code == ExitCode.RUN_ERROR
    assert error_line.startswith(
        f"[klint] Error: '{outside}' is not in a git repository"
    )
    assert judge.requests == []


@pytest.mark.parametrize(
    "argv",
    [
        ["klint", "--diff", "cart.py"],
        ["klint", "--diff-units", "all", "cart.py"],
        ["klint"],
        ["klint", "--diff", "--diff-units", "some"],
    ],
)
def test_a_diff_command_line_that_does_not_fit_exits_with_status_2(
    monkeypatch: pytest.MonkeyPatch, argv: list[str]
) -> None:
    monkeypatch.setattr(sys, "argv", argv)

    with pytest.raises(SystemExit) as stopped:
        run_file_audit()

    assert stopped.value.code == ExitCode.RUN_ERROR
