"""A project for the klint-mcp tests: its klint.json names the tests' rules."""

import os
from pathlib import Path

import pytest

from tests.support.builders import FILE_RULE, write_json, write_text
from tests.support.git_repository import commit_everything, isolate_git, run_git

# The project's rules: one for files, one for classes, one for functions and
# one for directories, so that every unit is asked exactly one rule.
PROJECT_RULES = {
    "tidy_file": FILE_RULE,
    "focused": {**FILE_RULE, "unit_types": ["class"]},
    "short": {**FILE_RULE, "unit_types": ["function"]},
    "tidy_directory": {**FILE_RULE, "unit_types": ["project_directory"]},
}

# A file with one function and one class, so that the file audit has units
# of each kind to select among.
CART_SOURCE = '''import json


class Cart:
    """A shopping cart."""

    def total(self) -> int:
        return sum(len(item) for item in self.items)


def load(text: str) -> Cart:
    return json.loads(text)
'''


@pytest.fixture
def project(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    """Return a project, as the server's working directory and the cwd.

    Its klint.json chooses the remote judge and replaces the built-in packs
    with the rules.json beside it, so that every unit is asked one rule.
    No klint setting from the shell reaches the test.
    """
    for name in list(os.environ):
        if name.startswith(("KLINT_", "KEV_")):
            monkeypatch.delenv(name)
    monkeypatch.setenv("KLINT_ANSWER_CACHE", "off")
    project = tmp_path / "shop"
    write_text(project / "cart.py", CART_SOURCE)
    rules = write_json(tmp_path / "rules.json", PROJECT_RULES)
    write_json(
        project / "klint.json",
        {
            "env": {
                "KLINT_JUDGE_MODE": "remote",
                "KLINT_REPLACE_FILE_RULES": str(rules),
                "KLINT_REPLACE_PROJECT_RULES": str(rules),
            }
        },
    )
    monkeypatch.chdir(project)
    return project


@pytest.fixture
def repository(project: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    """Return the project as a git repository with its files committed."""
    isolate_git(monkeypatch, tmp_path)
    run_git(project, "init", "--quiet", "--initial-branch", "main")
    commit_everything(project, "Starting the project")
    return project
