"""The answer scale the code suite's kinds of audit send to the judge."""

import asyncio
import json
from pathlib import Path

import pytest

from klint.cli.file_audit import FILE_AUDIT_COMMAND
from klint.cli.runner import AuditCommand
from klint.cli.structure_audit import STRUCTURE_AUDIT_COMMAND
from tests.support.builders import build_audit_command_app, write_text
from tests.support.fakes import FakeJudge

EXPECTED_CRITERIA = {
    "pass": "The provided content follows the described practice.",
    "fail": "The provided content violates the described practice.",
    "irrelevant": "The described practice does not apply to the provided content.",
    "lack_of_evidence": (
        "There is not enough information in the provided content to determine "
        "pass, fail, or irrelevance."
    ),
}


@pytest.mark.parametrize("command", [FILE_AUDIT_COMMAND, STRUCTURE_AUDIT_COMMAND])
def test_both_commands_send_these_criteria_to_the_judge_in_this_order(
    tmp_path: Path, fake_judge: type[FakeJudge], command: AuditCommand
) -> None:
    write_text(tmp_path / "a.py", "x = 1\n")
    judge = fake_judge()
    app = build_audit_command_app(command, judge)

    asyncio.run(app.run([str(tmp_path), "--json"]))

    assert judge.requests
    for request in judge.requests:
        for question in request.questions:
            criteria = question.choice_key_to_criterion
            assert list(criteria.items()) == list(EXPECTED_CRITERIA.items())


def test_labels_are_unchanged_and_only_fail_counts_as_a_problem(
    tmp_path: Path, fake_judge: type[FakeJudge], capsys: pytest.CaptureFixture[str]
) -> None:
    target = write_text(tmp_path / "a.py", "x = 1\n")

    key_to_label_and_exit_code: dict[str, tuple[str, int]] = {}
    for key in EXPECTED_CRITERIA:
        app = build_audit_command_app(FILE_AUDIT_COMMAND, fake_judge(default=key))
        exit_code = asyncio.run(app.run([str(target), "--all-answers", "--json"]))
        (issue,) = json.loads(capsys.readouterr().out)["findings"]
        key_to_label_and_exit_code[key] = (issue["answer"], int(exit_code))

    assert key_to_label_and_exit_code == {
        "pass": ("Pass", 0),
        "fail": ("Fail", 1),
        "irrelevant": ("Irrelevant", 0),
        "lack_of_evidence": ("Lack of Evidence", 0),
    }
