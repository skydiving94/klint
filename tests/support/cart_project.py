"""A small shop project, and the rules, that the tests of change audits share."""

import asyncio
from pathlib import Path
from typing import Any

import pytest

from klint.app import AppSettings
from klint.cli import FILE_AUDIT_COMMAND, ExitCode
from klint.core.interfaces import BaseJudge
from tests.support.builders import (
    FILE_RULE,
    build_audit_command_app,
    make_settings,
    write_json,
)
from tests.support.git_repository import create_repository, isolate_git

CLASS_RULE = {**FILE_RULE, "unit_types": ["class"]}
FUNCTION_RULE = {**FILE_RULE, "unit_types": ["function"]}
ALL_RULES = {"tidy_file": FILE_RULE, "focused": CLASS_RULE, "short": FUNCTION_RULE}

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
HELPERS = "def shout(text: str) -> str:\n    return text.upper()\n"
GO_BEFORE = "package main\n\nfunc main() {}\n"


def build_cart_settings(tmp_path: Path, **rules: dict[str, Any]) -> AppSettings:
    """Return settings whose one built-in pack holds ``rules``, or every rule."""
    pack = write_json(tmp_path / "rules.json", rules or ALL_RULES)
    return make_settings(built_in_rule_packs=[pack], fallback_rule_packs=[pack])


def run_file_command(
    judge: BaseJudge, settings: AppSettings, *options: str
) -> ExitCode:
    """Run the klint command with ``options`` and the judge given."""
    app = build_audit_command_app(FILE_AUDIT_COMMAND, judge, settings)
    return asyncio.run(app.run(list(options)))


def create_cart_repository(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    """Return a repository holding a cart module, a Go file and a helper, as the cwd."""
    isolate_git(monkeypatch, tmp_path)
    repository = create_repository(
        tmp_path / "shop",
        {"cart.py": CART_BEFORE, "helpers.py": HELPERS, "main.go": GO_BEFORE},
    )
    monkeypatch.chdir(repository)
    return repository
