"""Case sets for tests of the code-unit scoring command, and a way to run it."""

import asyncio
import json
from pathlib import Path

from judge_accuracy.code_units.scoring_command import ScoringExitCode, run_scoring
from klint.core.interfaces import BaseJudge
from klint.core.models.judging import JudgeAnswer, JudgeRequest
from tests.support.builders import write_text
from tests.support.fakes import FakeJudge, JudgeBindingOverride

PlantedProblemData = dict[str, str]

# A short module: a function that reads a user by ID, its columns named.
SHORT_MODULE = '''"""Reads users."""


async def find_user(database, user_id: int) -> dict:
    """Return the user ``user_id``."""
    return await database.fetch_one(
        "SELECT id, name FROM users WHERE id = ?", (user_id,)
    )
'''
SELECT_ALL_PROBLEM: PlantedProblemData = {
    "rule_id": "over_fetching_data",
    "old_text": '"SELECT id, name FROM users WHERE id = ?"',
    "new_text": '"SELECT * FROM users WHERE id = ?"',
    "why_wrong": "find_user reads every column.",
}


def build_long_module(step_count: int = 120) -> str:
    """Return a module whose one function runs ``step_count`` lines past 2,000."""
    steps = "".join(
        f"    total_{index} = await database.count_rows('table_{index}')\n"
        for index in range(step_count)
    )
    return (
        '"""Counts rows."""\n\n\n'
        "async def count_everything(database) -> int:\n"
        '    """Return the rows of every table."""\n'
        f"{steps}"
        "    return total_0\n"
    )


def write_case_module(
    folder: Path, name: str, source: str, *planted_problems: PlantedProblemData
) -> Path:
    """Write the case module ``name`` of ``source`` and ``planted_problems``."""
    write_text(
        folder / f"{name}.json",
        json.dumps({"schema_version": 1, "planted_problems": list(planted_problems)}),
    )
    return write_text(folder / f"{name}.py", source)


class MarkerJudge(FakeJudge):
    """Fails a rule on each subject that holds its marker; passes the others.

    long_true_failure, when set, is the rule it fails on every subject
    longer than 2,000 characters, as a judge that loses its way on long text.
    """

    def __init__(
        self,
        rule_id_to_marker: dict[str, str],
        long_true_failure: str | None = None,
    ) -> None:
        super().__init__()
        self._rule_id_to_marker = rule_id_to_marker
        self._long_true_failure = long_true_failure

    async def answer(self, request: JudgeRequest) -> list[JudgeAnswer]:
        self.requests.append(request)
        answers = []
        for question in request.questions:
            marker = self._rule_id_to_marker.get(question.question_id)
            is_failed = (marker is not None and marker in request.subject) or (
                question.question_id == self._long_true_failure
                and len(request.subject) > 2_000
            )
            choice = "fail" if is_failed else "pass"
            answers.append(
                JudgeAnswer(
                    question_id=question.question_id,
                    choice_key=choice,
                    confidence=0.9,
                    choice_key_to_probability={choice: 0.9},
                )
            )
        return answers


def run_code_unit_scoring(judge: BaseJudge, *arguments: str | Path) -> ScoringExitCode:
    """Run the code-unit scoring command with ``arguments``, asking ``judge``."""
    return asyncio.run(
        run_scoring(
            [str(argument) for argument in arguments], JudgeBindingOverride(judge)
        )
    )
