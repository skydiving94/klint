"""A project's klint.json turns one rule off for the paths a glob matches."""

import asyncio
import json
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest

from klint.app import AppSettings
from klint.cli import FILE_AUDIT_COMMAND
from klint.core import KlintWarning
from tests.support.builders import (
    FILE_RULE,
    build_audit_command_app,
    write_json,
    write_text,
)
from tests.support.fakes import FakeJudge

Capture = pytest.CaptureFixture[str]

RULES = {
    "tidy_rule": FILE_RULE,
    "short_rule": {**FILE_RULE, "question": "Is it short?"},
    "small_function_rule": {
        **FILE_RULE,
        "question": "Is it small?",
        "unit_types": ["function"],
    },
}
REASON = "https://github.com/example/project/pull/1#issuecomment-1"


def _audit_project(
    project: Path, rule_exclusions: list[Any], *arguments: str
) -> dict[str, set[str]]:
    """Run klint on ``project``, whose klint.json holds ``rule_exclusions``.

    The only rules are those of its klint.json. Return the rule IDs asked
    about each unit, by what the judge was shown.
    """
    write_json(
        project / "klint.json", {"rule_exclusions": rule_exclusions, "rules": RULES}
    )
    settings = replace(
        AppSettings.from_env(project), built_in_rule_packs=(), fallback_rule_packs=()
    )
    judge = FakeJudge()
    app = build_audit_command_app(FILE_AUDIT_COMMAND, judge, settings)
    asyncio.run(app.run([str(project), *arguments]))
    return judge.map_subject_to_asked_rule_ids()


def _exclusion(rule_id: str, *paths: str) -> dict[str, Any]:
    return {"rule_id": rule_id, "paths": list(paths), "reason": REASON}


@pytest.mark.usefixtures("shell_env")
def test_an_excluded_rule_is_not_asked_where_its_glob_matches(tmp_path: Path) -> None:
    project = tmp_path / "project"
    write_text(project / "legacy" / "old.py", "old = 1\n")
    write_text(project / "new.py", "new = 1\n")

    subject_to_rule_ids = _audit_project(
        project, [_exclusion("tidy_rule", "legacy/**")], "--json"
    )

    assert subject_to_rule_ids == {
        "old = 1\n": {"short_rule"},
        "new = 1\n": {"tidy_rule", "short_rule"},
    }


@pytest.mark.usefixtures("shell_env")
def test_a_function_is_matched_by_its_files_path(tmp_path: Path) -> None:
    project = tmp_path / "project"
    write_text(project / "gen" / "made.py", "def made():\n    return 1\n")
    write_text(project / "kept.py", "def kept():\n    return 2\n")

    subject_to_rule_ids = _audit_project(
        project, [_exclusion("small_function_rule", "gen/*.py")], "--json"
    )

    asked_function_rule_subjects = {
        subject
        for subject, rule_ids in subject_to_rule_ids.items()
        if "small_function_rule" in rule_ids
    }
    assert asked_function_rule_subjects == {"def kept():\n    return 2"}


@pytest.mark.usefixtures("shell_env")
def test_json_lists_each_applied_exclusion_with_its_units(
    tmp_path: Path, capsys: Capture
) -> None:
    project = tmp_path / "project"
    write_text(project / "legacy" / "old.py", "old = 1\n")
    write_text(project / "new.py", "new = 1\n")

    _audit_project(
        project,
        [_exclusion("tidy_rule", "legacy/**"), _exclusion("short_rule", "absent/**")],
        "--json",
    )

    report = json.loads(capsys.readouterr().out)
    assert report["applied_rule_exclusions"] == [
        {
            "rule_id": "tidy_rule",
            "paths": ["legacy/**"],
            "reason": REASON,
            "unit_ids": [str(project / "legacy" / "old.py")],
        }
    ]


@pytest.mark.usefixtures("shell_env")
def test_the_terminal_report_names_each_applied_exclusion(
    tmp_path: Path, capsys: Capture
) -> None:
    project = tmp_path / "project"
    write_text(project / "legacy" / "old.py", "old = 1\n")

    _audit_project(project, [_exclusion("tidy_rule", "legacy/**")])

    out = capsys.readouterr().out
    assert "Rules excluded by the project's klint.json:" in out
    assert f"tidy_rule\x1b[0m on legacy/** (1 unit(s)): {REASON}" in out


@pytest.mark.usefixtures("shell_env")
def test_json_is_unchanged_when_no_exclusion_applies(
    tmp_path: Path, capsys: Capture
) -> None:
    project = tmp_path / "project"
    write_text(project / "new.py", "new = 1\n")

    _audit_project(project, [_exclusion("tidy_rule", "legacy/**")], "--json")

    assert "applied_rule_exclusions" not in json.loads(capsys.readouterr().out)


@pytest.mark.usefixtures("shell_env")
@pytest.mark.parametrize(
    ("entry", "problem"),
    [
        ("not an object", "it must be an object with exactly"),
        (
            {"rule_id": "tidy_rule", "paths": ["**"]},
            "it must be an object with exactly",
        ),
        (
            {**_exclusion("tidy_rule"), "paths": []},
            "its 'paths' must be a list of globs",
        ),
        ({**_exclusion("tidy_rule", "**"), "rule_id": ""}, "'rule_id' must be"),
        ({**_exclusion("tidy_rule", "**"), "reason": " "}, "'reason' must say why"),
    ],
)
def test_an_unusable_entry_is_left_out_with_a_warning(
    tmp_path: Path, entry: object, problem: str
) -> None:
    project = tmp_path / "project"
    write_text(project / "new.py", "new = 1\n")

    with pytest.warns(KlintWarning, match=problem):
        subject_to_rule_ids = _audit_project(project, [entry], "--json")

    assert subject_to_rule_ids == {"new = 1\n": {"tidy_rule", "short_rule"}}
