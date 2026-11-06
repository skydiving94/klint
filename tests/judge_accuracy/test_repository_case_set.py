"""The repository's change-summary set, as the scoring command reads it."""

import json
import re
import subprocess
from pathlib import Path

import pytest

from judge_accuracy.change_summary.case_set import MistakeKind
from judge_accuracy.change_summary.scores import SummaryGroup
from judge_accuracy.change_summary.scoring_command import (
    DEFAULT_CASE_SET,
    ScoringExitCode,
)
from tests.judge_accuracy.scoring import find_table_row, run_scoring_command
from tests.support.fakes import FakeJudge

Capture = pytest.CaptureFixture[str]
_SET_SIZE = re.compile(r"(\d+) true summaries, (\d+) planted mistakes")
_SHARE = re.compile(r"(\d+)/(\d+) \(\d+%\)")


@pytest.fixture
def case_commits(shell_env: dict[str, str], in_repo_root: Path) -> None:
    """Run from the repository root; skip where a case file's commit is not cloned."""
    del shell_env
    for path in DEFAULT_CASE_SET.glob("*.json"):
        document = json.loads(path.read_text(encoding="utf-8"))["true_document"]
        commit = document.get("git_change", {}).get("commit")
        if commit is None:
            continue
        found = subprocess.run(
            ["git", "cat-file", "-e", f"{commit}^{{commit}}"],
            cwd=in_repo_root,
            capture_output=True,
            check=False,
        )
        if found.returncode != 0:
            pytest.skip(f"commit {commit} is not in this clone, as in a shallow one")


def _read_share_whole(cell: str) -> int:
    match = _SHARE.fullmatch(cell)
    assert match is not None, cell
    return int(match.group(2))


@pytest.mark.usefixtures("case_commits")
def test_the_set_holds_every_level_and_kind_of_mistake(capsys: Capture) -> None:
    exit_code = run_scoring_command(FakeJudge(default="inaccurate"))

    report = capsys.readouterr().out
    assert exit_code == ScoringExitCode.SCORED
    size = _SET_SIZE.search(report)
    assert size is not None
    true_count, planted_count = int(size.group(1)), int(size.group(2))
    assert true_count + planted_count >= 50
    assert "Refused: 0." in report
    for kind in MistakeKind:
        row = find_table_row(report, kind.value.replace("_", " ").capitalize())
        assert int(row[1]) > 0, kind
    # Each group, hunks over the cut included, holds planted and true summaries.
    for group in SummaryGroup:
        _, caught, wrongly_flagged = find_table_row(report, group.value)
        assert _read_share_whole(caught) > 0, group
        assert _read_share_whole(wrongly_flagged) > 0, group
