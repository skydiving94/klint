"""The commit gate applies a klint.json unit selector, and a diff never warns."""

from pathlib import Path

import pytest

from klint.cli import ExitCode
from tests.support.builders import write_json
from tests.support.fakes import SubjectJudge
from tests.support.git_repository import isolate_git
from tests.support.pre_commit import (
    CART_AFTER,
    find_total_source,
    read_entries,
    run_gate,
    set_up_gate_repository,
    stage,
)
from tests.support.rule_exclusions import build_exclusion

Capture = pytest.CaptureFixture[str]


@pytest.fixture
def repository(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, shell_env: dict[str, str]
) -> Path:
    del shell_env
    isolate_git(monkeypatch, tmp_path)
    return set_up_gate_repository(monkeypatch, tmp_path)


def _fail_total() -> SubjectJudge:
    return SubjectJudge({find_total_source(CART_AFTER): "fail"}, confidence=0.9)


def test_the_gate_skips_a_rule_a_selector_turns_off(
    repository: Path, capsys: Capture
) -> None:
    write_json(
        repository / "klint.json",
        {"rule_exclusions": [build_exclusion("short", "cart.py::Cart")]},
    )
    stage(repository, {"cart.py": CART_AFTER})

    exit_code = run_gate(_fail_total())

    assert exit_code == ExitCode.NO_PROBLEMS
    assert read_entries(repository) == []
    assert "Warning" not in capsys.readouterr().err


def test_the_gate_still_blocks_where_the_selector_does_not_reach(
    repository: Path,
) -> None:
    write_json(
        repository / "klint.json",
        {"rule_exclusions": [build_exclusion("short", "cart.py::Cart.add")]},
    )
    stage(repository, {"cart.py": CART_AFTER})

    exit_code = run_gate(_fail_total())

    assert exit_code == ExitCode.PROBLEMS_FOUND
    assert [entry["unit"]["name"] for entry in read_entries(repository)] == [
        "Cart.total"
    ]


def test_a_stale_selector_does_not_warn_in_a_diff_audit(
    repository: Path, capsys: Capture
) -> None:
    write_json(
        repository / "klint.json",
        {"rule_exclusions": [build_exclusion("short", "cart.py::Basket")]},
    )
    stage(repository, {"cart.py": CART_AFTER})

    run_gate(_fail_total())

    assert "Warning" not in capsys.readouterr().err
