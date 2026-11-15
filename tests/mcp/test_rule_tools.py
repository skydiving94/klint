"""The list_rules and explain_rule tools: what a path is asked, and why."""

from pathlib import Path

from klint.mcp import create_mcp_server
from tests.support.builders import write_json, write_text
from tests.support.mcp_client import call_tool


def test_list_rules_lists_each_rule_a_file_is_asked_with_its_units(
    project: Path,
) -> None:
    server = create_mcp_server(project)

    call = call_tool(server, "list_rules", {"path": "cart.py"})

    assert not call.result.is_error
    assert call.read_content() == {
        "path": "cart.py",
        "rules": [
            {
                "tool": "audit_files",
                "rule_id": "tidy_file",
                "question": "Is it tidy?",
                "unit_types": ["file"],
                "tags": [],
                "unit_ids": ["cart.py"],
            },
            {
                "tool": "audit_files",
                "rule_id": "focused",
                "question": "Is it tidy?",
                "unit_types": ["class"],
                "tags": [],
                "unit_ids": ["cart.py::Cart"],
            },
            {
                "tool": "audit_files",
                "rule_id": "short",
                "question": "Is it tidy?",
                "unit_types": ["function"],
                "tags": [],
                "unit_ids": ["cart.py::Cart.total", "cart.py::load"],
            },
        ],
        "applied_rule_exclusions": [],
    }


def test_list_rules_for_a_directory_covers_both_code_audits(project: Path) -> None:
    write_text(project / "app" / "__init__.py", "")
    server = create_mcp_server(project)

    call = call_tool(server, "list_rules", {"path": "."})

    content = call.read_content()
    assert [
        (rule["tool"], rule["rule_id"], rule["unit_ids"]) for rule in content["rules"]
    ] == [
        ("audit_files", "tidy_file", ["app/__init__.py", "cart.py"]),
        ("audit_files", "focused", ["cart.py::Cart"]),
        ("audit_files", "short", ["cart.py::Cart.total", "cart.py::load"]),
        ("audit_structure", "tidy_directory", [".", "app"]),
    ]


def test_list_rules_leaves_out_a_rule_the_project_excludes(project: Path) -> None:
    write_json(
        project / "klint.json",
        {
            "env": {
                "KLINT_JUDGE_MODE": "remote",
                "KLINT_REPLACE_FILE_RULES": str(project.parent / "rules.json"),
            },
            "rule_exclusions": [
                {"rule_id": "tidy_file", "paths": ["cart.py"], "reason": "a demo"}
            ],
        },
    )
    server = create_mcp_server(project)

    call = call_tool(server, "list_rules", {"path": "cart.py"})

    content = call.read_content()
    assert [rule["rule_id"] for rule in content["rules"]] == ["focused", "short"]
    assert content["applied_rule_exclusions"] == [
        {
            "rule_id": "tidy_file",
            "paths": ["cart.py"],
            "reason": "a demo",
            "unit_ids": ["cart.py"],
        }
    ]


def test_explain_rule_gives_its_question_unit_types_scope_and_pack(
    project: Path,
) -> None:
    server = create_mcp_server(project)

    call = call_tool(server, "explain_rule", {"rule_id": "tidy_directory"})

    assert not call.result.is_error
    assert call.read_content() == {
        "rule_id": "tidy_directory",
        "definitions": [
            {
                "tool": "audit_files",
                "pack": str(project.parent / "rules.json"),
                "pack_languages": None,
                "question": "Is it tidy?",
                "question_with_layers": None,
                "unit_type_to_question": {},
                "unit_types": ["project_directory"],
                "languages": [],
                "unit_tags": [],
                "excluded_unit_tags": [],
                "tags": [],
            },
            {
                "tool": "audit_structure",
                "pack": str(project.parent / "rules.json"),
                "pack_languages": None,
                "question": "Is it tidy?",
                "question_with_layers": None,
                "unit_type_to_question": {},
                "unit_types": ["project_directory"],
                "languages": [],
                "unit_tags": [],
                "excluded_unit_tags": [],
                "tags": [],
            },
        ],
    }


def test_explain_rule_finds_a_change_summary_check(project: Path) -> None:
    server = create_mcp_server(project)

    call = call_tool(server, "explain_rule", {"rule_id": "no_false_statement"})

    content = call.read_content()
    assert [definition["tool"] for definition in content["definitions"]] == [
        "check_change_summary"
    ]
    assert content["definitions"][0]["pack"].endswith("summary_checks.json")


def test_explain_rule_names_an_unknown_rule(project: Path) -> None:
    server = create_mcp_server(project)

    call = call_tool(server, "explain_rule", {"rule_id": "no_such_rule"})

    assert call.result.is_error
    assert "No rule 'no_such_rule'" in call.read_error()
