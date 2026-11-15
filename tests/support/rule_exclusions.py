"""Running klint on a project whose klint.json holds rule exclusions."""

import asyncio
from dataclasses import replace
from pathlib import Path
from typing import Any

from klint.app import AppSettings
from klint.cli import FILE_AUDIT_COMMAND
from tests.support.builders import build_audit_command_app, write_json
from tests.support.fakes import FakeJudge

REASON = "https://github.com/example/project/pull/1#issuecomment-1"


def audit_project(
    project: Path,
    rules: dict[str, Any],
    rule_exclusions: list[Any],
    *arguments: str,
    target: Path | None = None,
) -> dict[str, set[str]]:
    """Run klint on ``project``, whose klint.json holds ``rule_exclusions``.

    The audit is of ``target``, inside ``project``, when given. The only
    rules are ``rules``, those of its klint.json. Return the rule IDs asked
    about each unit, by what the judge was shown.
    """
    write_json(
        project / "klint.json", {"rule_exclusions": rule_exclusions, "rules": rules}
    )
    settings = replace(
        AppSettings.from_env(project), built_in_rule_packs=(), fallback_rule_packs=()
    )
    judge = FakeJudge()
    app = build_audit_command_app(FILE_AUDIT_COMMAND, judge, settings)
    asyncio.run(app.run([str(target or project), *arguments]))
    return judge.map_subject_to_asked_rule_ids()


def build_exclusion(rule_id: str, *paths: str) -> dict[str, Any]:
    """Return a "rule_exclusions" entry turning ``rule_id`` off for ``paths``."""
    return {"rule_id": rule_id, "paths": list(paths), "reason": REASON}
