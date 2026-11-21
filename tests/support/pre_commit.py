"""A repository and the settings for running klint-pre-commit and klint-ack in tests."""

import asyncio
import json
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import pytest

from klint.cli import ExitCode, PreCommitGate, acknowledge_entry
from klint.core.interfaces import BaseJudge
from tests.support.builders import FILE_RULE, write_json
from tests.support.fakes import JudgeBindingOverride
from tests.support.git_repository import create_repository, run_git, write_files

CLASS_RULE = {**FILE_RULE, "unit_types": ["class"]}
FUNCTION_RULE = {**FILE_RULE, "question": "Is it short?", "unit_types": ["function"]}
GATE_RULES = {"tidy_file": FILE_RULE, "focused": CLASS_RULE, "short": FUNCTION_RULE}

CART_BEFORE = '''import json


class Cart:
    """A shopping cart."""

    def add(self, item: str) -> None:
        self.items.append(item)

    def total(self) -> int:
        """Return the sum of the prices."""
        return sum(len(item) for item in self.items)


def load(text: str) -> Cart:
    return json.loads(text)
'''
# The total method gains a line: lines 12 and 13 are the changed ones.
CART_AFTER = CART_BEFORE.replace(
    "        return sum(len(item) for item in self.items)\n",
    "        prices = [len(item) for item in self.items]\n        return sum(prices)\n",
)
# The total method changes again, so its code hashes differently.
CART_CHANGED_AGAIN = CART_AFTER.replace("prices = [", "prices = [1 + ")
HELPERS = "def shout(text: str) -> str:\n    return text.upper()\n"
HELPERS_AFTER = HELPERS.replace("upper", "lower")
# The folder of the log, from the repository's root.
LOG_FOLDER = Path(".klint") / "acknowledgements"


def find_total_source(cart: str) -> str:
    """Return the source of the total method in ``cart``, as the judge is shown it."""
    lines = cart.splitlines()
    first = next(index for index, line in enumerate(lines) if "def total" in line)
    end = next(index for index, line in enumerate(lines) if line.startswith("def "))
    return "\n".join(line[4:] for line in lines[first:end]).rstrip()


def set_up_gate_repository(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, model_name: str = "fake"
) -> Path:
    """Return a repository holding a cart module and a helper, as the cwd.

    The rules asked are the tests' own, and the judge is remote, so that the
    fake judge a test binds answers.
    """
    rules = write_json(tmp_path / "rules.json", GATE_RULES)
    monkeypatch.setenv("KLINT_REPLACE_FILE_RULES", str(rules))
    monkeypatch.setenv("KLINT_JUDGE_MODE", "remote")
    monkeypatch.setenv("KLINT_JUDGE_MODEL", model_name)
    repository = create_repository(
        tmp_path / "shop", {"cart.py": CART_BEFORE, "helpers.py": HELPERS}
    )
    monkeypatch.chdir(repository)
    return repository


def stage(repository: Path, path_to_content: dict[str, str]) -> None:
    """Write each file and stage it."""
    write_files(repository, path_to_content)
    run_git(repository, "add", "--", *path_to_content)


def run_gate(judge: BaseJudge, *options: str) -> ExitCode:
    """Run klint-pre-commit in the cwd's repository with ``judge``."""
    return asyncio.run(PreCommitGate(JudgeBindingOverride(judge)).run(list(options)))


def run_ack(*options: str) -> ExitCode:
    """Run klint-ack in the cwd's repository."""
    return asyncio.run(acknowledge_entry(list(options), Path.cwd()))


def run_ack_with_judge(judge: BaseJudge, *options: str) -> ExitCode:
    """Run klint-ack in the cwd's repository, with ``judge`` wired in."""
    return asyncio.run(
        acknowledge_entry(list(options), Path.cwd(), JudgeBindingOverride(judge))
    )


def list_entry_files(repository: Path) -> list[Path]:
    folder = repository / LOG_FOLDER
    return sorted(folder.glob("*.json")) if folder.is_dir() else []


def read_entries(repository: Path) -> list[dict[str, Any]]:
    """Return every entry of the repository's log, in file name order."""
    return [
        json.loads(path.read_text(encoding="utf-8"))
        for path in list_entry_files(repository)
    ]


def list_staged_paths(repository: Path) -> list[str]:
    """Return the paths the index differs from HEAD on."""
    return run_git(repository, "diff", "--cached", "--name-only").split()


def find_ack_commands(output: str) -> Sequence[str]:
    """Return each klint-ack command line a blocked commit's message gives."""
    return [
        line.strip()
        for line in output.splitlines()
        if line.strip().startswith("klint-ack ")
    ]
