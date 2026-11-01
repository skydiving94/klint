"""Rules limited to unit tags, asked by the tags detected for each file."""

import asyncio
import json
from pathlib import Path

import pytest

from klint.cli.file_audit import FILE_AUDIT_COMMAND
from klint.cli.runner import AuditCommand
from klint.cli.structure_audit import STRUCTURE_AUDIT_COMMAND
from tests.support.builders import (
    FILE_RULE,
    build_audit_command_app,
    make_settings,
    write_json,
    write_text,
)
from tests.support.fakes import FakeJudge
from tests.support.paths import (
    BUILT_IN_RULE_PACKS,
    FALLBACK_RULE_PACKS,
    REACT_RULE_PACK,
)

TAGGED_RULES = {
    "backend_rule": {**FILE_RULE, "unit_tags": ["backend"]},
    "frontend_rule": {**FILE_RULE, "unit_tags": ["frontend"]},
    "any_rule": FILE_RULE,
}


def _audit_files(
    target: Path, custom_rules_path: Path, command: AuditCommand = FILE_AUDIT_COMMAND
) -> dict[str, set[str]]:
    """Run ``command`` on ``target`` with only the rules in ``custom_rules_path``.

    Return the rule IDs asked about each unit, by what the judge read.
    """
    judge = FakeJudge()
    # No rule but the custom ones.
    settings = make_settings(built_in_rule_packs=[], fallback_rule_packs=[])
    app = build_audit_command_app(command, judge, settings)
    asyncio.run(app.run([str(target), "--json", "--rules", str(custom_rules_path)]))
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


def test_imports_at_the_start_of_a_file_tag_it(tmp_path: Path) -> None:
    rules = write_json(tmp_path / "rules.json", TAGGED_RULES)
    write_text(tmp_path / "repo" / "lib" / "db.py", "import sqlalchemy\n")
    write_text(tmp_path / "repo" / "lib" / "view.js", "import React from 'react';\n")
    # Past the start that is read: the import is not seen.
    write_text(
        tmp_path / "repo" / "lib" / "late.py", "#\n" * 3000 + "import sqlalchemy\n"
    )

    content_to_rule_ids = _audit_files(tmp_path / "repo", rules)

    assert content_to_rule_ids["import sqlalchemy\n"] == {"backend_rule", "any_rule"}
    assert content_to_rule_ids["import React from 'react';\n"] == {
        "frontend_rule",
        "any_rule",
    }
    late_rule_ids = [
        rule_ids
        for content, rule_ids in content_to_rule_ids.items()
        if content.startswith("#\n")
    ]
    assert late_rule_ids == [{"backend_rule", "frontend_rule", "any_rule"}]


def test_project_audit_tags_the_files_of_a_directory_alike(tmp_path: Path) -> None:
    file_metadata_rule = {**FILE_RULE, "unit_types": ["file_metadata"]}
    rules = write_json(
        tmp_path / "rules.json",
        {"frontend_file": {**file_metadata_rule, "unit_tags": ["frontend"]}},
    )
    write_text(tmp_path / "repo" / "db.py", "import sqlalchemy\n")
    write_text(tmp_path / "repo" / "view.js", "import React from 'react';\n")

    content_to_rule_ids = _audit_files(
        tmp_path / "repo", rules, STRUCTURE_AUDIT_COMMAND
    )

    # Only the file that imports React is asked the frontend rule.
    assert content_to_rule_ids == {"view.js (lines=1)": {"frontend_file"}}


@pytest.mark.usefixtures("in_repo_root")
def test_examples_are_asked_the_built_in_rules_of_their_side() -> None:
    judge = FakeJudge()
    settings = make_settings(BUILT_IN_RULE_PACKS, FALLBACK_RULE_PACKS)
    app = build_audit_command_app(FILE_AUDIT_COMMAND, judge, settings)
    asyncio.run(app.run(["examples", "--json"]))
    content_to_rule_ids = judge.subject_to_asked_rule_ids()
    backend_rule_ids = set(_read_rule_ids(BUILT_IN_RULE_PACKS[0]))
    react_rule_ids = set(_read_rule_ids(REACT_RULE_PACK))

    def asked_rule_ids(example: str) -> set[str]:
        (rule_ids,) = [
            rule_ids
            for content, rule_ids in content_to_rule_ids.items()
            if Path(example)
            .read_text(encoding="utf-8")
            .startswith(content.split("\n[... ")[0])
        ]
        return rule_ids

    for example in (
        "examples/frontend_architecture.tsx",
        "examples/frontend_hooks_and_dom.tsx",
    ):
        assert asked_rule_ids(example) == react_rule_ids | {"god_component"}
    for example in (
        "examples/backend_data_and_security.py",
        "examples/mock_bad_project/api/checkout_routes.py",
        # Backend by its import of sqlite3 alone.
        "examples/mock_bad_project/domain/order_entity.py",
        # No signal: every rule for its language.
        "examples/mock_bad_project/utils/misc_helpers.py",
    ):
        assert asked_rule_ids(example) == backend_rule_ids | {"god_component"}


def _read_rule_ids(pack: Path) -> list[str]:
    rules: dict[str, object] = json.loads(pack.read_text(encoding="utf-8"))["rules"]
    return list(rules)
