"""klint-pre-commit: the staged change passes, or open findings block the commit."""

from pathlib import Path

import pytest

from klint.cli import ExitCode
from tests.support.fakes import FakeJudge, PickyJudge, SubjectJudge
from tests.support.git_repository import isolate_git, run_git
from tests.support.pre_commit import (
    CART_AFTER,
    CART_BEFORE,
    CART_CHANGED_AGAIN,
    HELPERS_AFTER,
    LOG_FOLDER,
    find_ack_commands,
    find_total_source,
    list_entry_files,
    list_staged_paths,
    read_entries,
    run_ack,
    run_gate,
    set_up_gate_repository,
    stage,
)

Capture = pytest.CaptureFixture[str]


@pytest.fixture
def repository(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, shell_env: dict[str, str]
) -> Path:
    del shell_env
    isolate_git(monkeypatch, tmp_path)
    return set_up_gate_repository(monkeypatch, tmp_path)


def _build_failing_judge(*cart_versions: str) -> SubjectJudge:
    """Return a judge that fails the total method of each ``cart_versions``."""
    return SubjectJudge(
        {find_total_source(cart): "fail" for cart in cart_versions}, confidence=0.9
    )


def test_a_change_with_no_finding_passes_and_writes_no_log(
    repository: Path, capsys: Capture
) -> None:
    stage(repository, {"cart.py": CART_AFTER})

    exit_code = run_gate(FakeJudge())

    assert exit_code == ExitCode.NO_PROBLEMS
    assert capsys.readouterr().out.splitlines() == [
        "[klint-pre-commit] Staged change passes: 3 units checked, no open finding "
        "(confidence 0.8 or more, judge fake)"
    ]
    assert not (repository / LOG_FOLDER).exists()
    assert list_staged_paths(repository) == ["cart.py"]


def test_a_finding_blocks_the_commit_and_is_logged_open_and_staged(
    repository: Path, capsys: Capture
) -> None:
    stage(repository, {"cart.py": CART_AFTER})

    exit_code = run_gate(_build_failing_judge(CART_AFTER))

    output = capsys.readouterr().out
    assert exit_code == ExitCode.PROBLEMS_FOUND
    [entry] = read_entries(repository)
    [entry_file] = list_entry_files(repository)
    assert entry_file.name == f"{entry['id']}.json"
    assert entry == {
        "id": entry["id"],
        "rule_id": "short",
        "file": "cart.py",
        "unit": {
            "kind": "function",
            "name": "Cart.total",
            "start_line": 10,
            "end_line": 13,
        },
        "code_hash": entry["code_hash"],
        "finding": {"answer": "Fail", "question": "Is it short?", "confidence": 0.9},
        "judge_model_version": "fake-model-1",
        "first_flagged_at": entry["first_flagged_at"],
        "status": "open",
        "acknowledged_at": None,
        "note": None,
    }
    assert entry["code_hash"].startswith("sha256:")
    assert len(entry["id"]) == 12
    assert output.splitlines()[0] == (
        "[klint-pre-commit] Commit blocked: 1 finding in the staged change needs a "
        "fix or an acknowledgement (confidence 0.8 or more, judge fake)"
    )
    assert (
        f"  {entry['id']}  short  cart.py::Cart.total (lines 10-13)  confidence 90.0%"
    )
    assert find_ack_commands(output) == [
        f'klint-ack {entry["id"]} --note "<why this finding is wrong>"'
    ]
    assert "git commit --no-verify skips this check" in output
    assert list_staged_paths(repository) == [
        f".klint/acknowledgements/{entry['id']}.json",
        "cart.py",
    ]


def test_the_same_change_gives_the_same_entry(repository: Path) -> None:
    stage(repository, {"cart.py": CART_AFTER})
    judge = _build_failing_judge(CART_AFTER)

    run_gate(judge)
    [first_entry] = read_entries(repository)
    run_gate(judge)

    assert read_entries(repository) == [first_entry]


def test_an_acknowledged_finding_on_unchanged_code_no_longer_blocks(
    repository: Path, capsys: Capture
) -> None:
    stage(repository, {"cart.py": CART_AFTER})
    judge = _build_failing_judge(CART_AFTER)
    run_gate(judge)
    [entry] = read_entries(repository)
    capsys.readouterr()

    ack_exit_code = run_ack(entry["id"], "--note", "total is three lines long")
    ack_output = capsys.readouterr().out
    exit_code = run_gate(judge)

    output = capsys.readouterr().out
    assert ack_exit_code == ExitCode.NO_PROBLEMS
    assert ack_output.splitlines() == [
        f"[klint-ack] Acknowledged {entry['id']}: short on cart.py::Cart.total "
        f"(lines 10-13); staged .klint/acknowledgements/{entry['id']}.json"
    ]
    assert exit_code == ExitCode.NO_PROBLEMS
    assert output.splitlines() == [
        "[klint-pre-commit] Staged change passes: 3 units checked, no open finding "
        "(confidence 0.8 or more, judge fake)",
        "1 finding matches an acknowledged entry and is not reported",
    ]
    [acknowledged] = read_entries(repository)
    assert acknowledged["status"] == "acknowledged"
    assert acknowledged["note"] == "total is three lines long"
    assert acknowledged["acknowledged_at"] is not None
    assert acknowledged["first_flagged_at"] == entry["first_flagged_at"]


def test_an_acknowledged_finding_on_changed_code_is_flagged_again(
    repository: Path, capsys: Capture
) -> None:
    stage(repository, {"cart.py": CART_AFTER})
    judge = _build_failing_judge(CART_AFTER, CART_CHANGED_AGAIN)
    run_gate(judge)
    [entry] = read_entries(repository)
    run_ack(entry["id"], "--note", "fine as it is")
    stage(repository, {"cart.py": CART_CHANGED_AGAIN})
    capsys.readouterr()

    exit_code = run_gate(judge)

    assert exit_code == ExitCode.PROBLEMS_FOUND
    entries = {e["id"]: e for e in read_entries(repository)}
    assert len(entries) == 2
    old_entry = entries.pop(entry["id"])
    [new_entry] = entries.values()
    assert old_entry["status"] == "acknowledged"
    assert new_entry["status"] == "open"
    assert new_entry["code_hash"] != old_entry["code_hash"]
    assert find_ack_commands(capsys.readouterr().out) == [
        f'klint-ack {new_entry["id"]} --note "<why this finding is wrong>"'
    ]


def test_a_fix_removes_the_open_entry_and_stages_its_removal(
    repository: Path, capsys: Capture
) -> None:
    stage(repository, {"cart.py": CART_AFTER})
    judge = _build_failing_judge(CART_AFTER)
    run_gate(judge)
    [entry] = read_entries(repository)
    run_git(repository, "commit", "--quiet", "--no-verify", "--message", "Bypassed")
    stage(repository, {"cart.py": CART_CHANGED_AGAIN})
    capsys.readouterr()

    exit_code = run_gate(judge)

    assert exit_code == ExitCode.NO_PROBLEMS
    assert read_entries(repository) == []
    assert "Removed 1 entry whose finding is gone" in capsys.readouterr().out
    assert list_staged_paths(repository) == [
        f".klint/acknowledgements/{entry['id']}.json",
        "cart.py",
    ]
    assert run_git(repository, "diff", "--cached", "--name-status").startswith("D")


def test_an_entry_for_a_unit_the_file_no_longer_holds_is_removed(
    repository: Path,
) -> None:
    stage(repository, {"cart.py": CART_AFTER})
    judge = _build_failing_judge(CART_AFTER)
    run_gate(judge)
    without_total = CART_AFTER[: CART_AFTER.index("    def total")] + (
        "\n" + CART_AFTER[CART_AFTER.index("def load") :]
    )
    stage(repository, {"cart.py": without_total})

    exit_code = run_gate(judge)

    assert exit_code == ExitCode.NO_PROBLEMS
    assert read_entries(repository) == []


def test_entries_outside_the_staged_change_are_left_alone(repository: Path) -> None:
    stage(repository, {"helpers.py": HELPERS_AFTER})
    run_gate(FakeJudge(rule_id_to_answer={"short": "fail"}))
    [helpers_entry] = read_entries(repository)
    run_git(repository, "reset", "--quiet")
    stage(repository, {"cart.py": CART_AFTER})

    exit_code = run_gate(FakeJudge())

    assert exit_code == ExitCode.NO_PROBLEMS
    assert read_entries(repository) == [helpers_entry]


def test_an_open_entry_in_a_staged_file_blocks_even_on_unchanged_lines(
    repository: Path, capsys: Capture
) -> None:
    stage(repository, {"cart.py": CART_AFTER})
    run_gate(_build_failing_judge(CART_AFTER))
    [entry] = read_entries(repository)
    run_git(repository, "commit", "--quiet", "--no-verify", "--message", "Bypassed")
    # The load function changes; total is not among the units judged.
    stage(repository, {"cart.py": CART_AFTER.replace("json.loads", "json.loads ")})
    capsys.readouterr()

    exit_code = run_gate(FakeJudge())

    assert exit_code == ExitCode.PROBLEMS_FOUND
    assert find_ack_commands(capsys.readouterr().out) == [
        f'klint-ack {entry["id"]} --note "<why this finding is wrong>"'
    ]


@pytest.mark.usefixtures("repository")
def test_nothing_staged_passes_without_asking_the_judge(capsys: Capture) -> None:
    judge = FakeJudge()

    exit_code = run_gate(judge)

    assert exit_code == ExitCode.NO_PROBLEMS
    assert capsys.readouterr().out.splitlines() == [
        "[klint-pre-commit] Nothing is staged, so there is nothing to check"
    ]
    assert judge.requests == []


def test_a_judge_that_is_down_blocks_the_commit_with_the_reason(
    repository: Path, capsys: Capture
) -> None:
    stage(repository, {"cart.py": CART_AFTER})

    exit_code = run_gate(PickyJudge(refuses="class Cart"))

    captured = capsys.readouterr()
    assert exit_code == ExitCode.RUN_ERROR
    assert captured.out == ""
    assert captured.err.splitlines()[-1] == (
        "[klint-pre-commit] Error: the staged change could not be checked: 2 of "
        "the 3 units could not be checked; cart.py because judge is down"
    )
    assert not (repository / LOG_FOLDER).exists()


def test_a_malformed_entry_file_blocks_the_commit_naming_it(
    repository: Path, capsys: Capture
) -> None:
    stage(repository, {"cart.py": CART_AFTER})
    bad_entry = repository / LOG_FOLDER / "bad.json"
    bad_entry.parent.mkdir(parents=True)
    bad_entry.write_text('{"id": "bad"}', encoding="utf-8")

    exit_code = run_gate(FakeJudge())

    assert exit_code == ExitCode.RUN_ERROR
    assert capsys.readouterr().err.splitlines()[-1] == (
        f"[klint-pre-commit] Error: The acknowledgement log entry '{bad_entry}' "
        "cannot be read: 'rule_id' must be a non-empty string"
    )


def test_outside_a_git_repository_the_commit_is_blocked_with_the_reason(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, shell_env: dict[str, str]
) -> None:
    del shell_env
    isolate_git(monkeypatch, tmp_path)
    set_up_gate_repository(monkeypatch, tmp_path)
    outside = tmp_path / "outside"
    outside.mkdir()
    monkeypatch.chdir(outside)

    assert run_gate(FakeJudge()) == ExitCode.RUN_ERROR


def test_the_unstaged_file_is_not_what_the_gate_reads_for_the_before(
    repository: Path,
) -> None:
    # Sanity: with the change not staged, nothing is checked.
    (repository / "cart.py").write_text(CART_AFTER, encoding="utf-8")

    assert run_gate(_build_failing_judge(CART_AFTER)) == ExitCode.NO_PROBLEMS
    assert CART_BEFORE != CART_AFTER
