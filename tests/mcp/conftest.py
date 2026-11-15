"""A project for the klint-mcp tests: its klint.json names the tests' rules."""

import os
from pathlib import Path

import pytest

from tests.support.builders import write_json, write_text
from tests.support.paths import TIDY_RULE_PACK

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
    with the tests' own, so that every file and every directory is asked a
    rule. No klint setting from the shell reaches the test.
    """
    for name in list(os.environ):
        if name.startswith(("KLINT_", "KEV_")):
            monkeypatch.delenv(name)
    monkeypatch.setenv("KLINT_ANSWER_CACHE", "off")
    project = tmp_path / "shop"
    write_text(project / "cart.py", CART_SOURCE)
    write_json(
        project / "klint.json",
        {
            "env": {
                "KLINT_JUDGE_MODE": "remote",
                "KLINT_REPLACE_FILE_RULES": str(TIDY_RULE_PACK),
                "KLINT_REPLACE_PROJECT_RULES": str(TIDY_RULE_PACK),
            }
        },
    )
    monkeypatch.chdir(project)
    return project
