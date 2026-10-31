"""Rules limited to unit tags, asked by the tags detected for each file."""

import asyncio
from pathlib import Path

from klint.cli.basic_audit import FILE_AUDIT_COMMAND
from tests.support.builders import (
    FILE_RULE,
    build_audit_command_app,
    make_settings,
    write_json,
    write_text,
)
from tests.support.fakes import FakeJudge

TAGGED_RULES = {
    "backend_rule": {**FILE_RULE, "unit_tags": ["backend"]},
    "frontend_rule": {**FILE_RULE, "unit_tags": ["frontend"]},
    "any_rule": FILE_RULE,
}


def _audit_files(target: Path, rules_path: Path) -> dict[str, set[str]]:
    """Run klint on ``target`` with only the rules in ``rules_path``.

    Return the rule IDs asked about each file, by the file's content.
    """
    judge = FakeJudge()
    # No rule but the custom ones.
    settings = make_settings(built_in_rule_packs=[], fallback_rule_packs=[])
    app = build_audit_command_app(FILE_AUDIT_COMMAND, judge, settings)
    asyncio.run(app.run([str(target), "--json", "--rules", str(rules_path)]))
    return judge.subject_to_asked_rule_ids()


def test_rules_limited_to_unit_tags_are_asked_where_the_tags_are_detected(
    tmp_path: Path,
) -> None:
    rules = write_json(tmp_path / "rules.json", TAGGED_RULES)
    write_text(tmp_path / "repo" / "api" / "orders.py", "orders = 1\n")
    write_text(tmp_path / "repo" / "web" / "View.tsx", "export {};\n")
    write_text(tmp_path / "repo" / "api" / "Form.tsx", "export const f = 1;\n")
    write_text(tmp_path / "repo" / "lib" / "util.py", "util = 1\n")

    content_to_rule_ids = _audit_files(tmp_path / "repo", rules)

    assert content_to_rule_ids == {
        # Backend by its folder.
        "orders = 1\n": {"backend_rule", "any_rule"},
        # Frontend by its extension.
        "export {};\n": {"frontend_rule", "any_rule"},
        # Both: any of its tags is enough.
        "export const f = 1;\n": {"backend_rule", "frontend_rule", "any_rule"},
        # No tag detected: every rule for its kind and language.
        "util = 1\n": {"backend_rule", "frontend_rule", "any_rule"},
    }


def test_folders_above_the_target_do_not_tag_its_files(tmp_path: Path) -> None:
    rules = write_json(tmp_path / "rules.json", TAGGED_RULES)
    write_text(tmp_path / "api" / "project" / "web" / "View.tsx", "export {};\n")

    content_to_rule_ids = _audit_files(tmp_path / "api" / "project", rules)

    assert content_to_rule_ids == {"export {};\n": {"frontend_rule", "any_rule"}}
