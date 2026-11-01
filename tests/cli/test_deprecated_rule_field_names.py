"""Old rule field names: each still works for one release, with a warning."""

import asyncio
from pathlib import Path

import pytest

from klint.cli.file_audit import FILE_AUDIT_COMMAND
from tests.support.builders import (
    build_audit_command_app,
    make_settings,
    write_json,
    write_text,
)
from tests.support.fakes import FakeJudge


def _describe_deprecation(old_name: str, new_name: str, rules_file: Path) -> str:
    return (
        f"[klint] Warning: '{old_name}' in '{rules_file}' is deprecated and "
        f"stops working in the next release; use '{new_name}' instead"
    )


def test_old_instructions_field_is_still_asked_with_one_warning_per_file(
    tmp_path: Path,
    fake_judge: type[FakeJudge],
    capsys: pytest.CaptureFixture[str],
) -> None:
    rules_file = write_json(
        tmp_path / "rules.json",
        {
            "first": {"type": "choice", "instructions": "Is it first?"},
            "second": {"type": "choice", "instructions": "Is it second?"},
            "both": {"type": "choice", "instructions": "Old?", "question": "New?"},
        },
    )
    target = write_text(tmp_path / "a.py", "x = 1\n")
    judge = fake_judge()
    settings = make_settings(built_in_rule_packs=[], fallback_rule_packs=[])
    app = build_audit_command_app(FILE_AUDIT_COMMAND, judge, settings)

    asyncio.run(app.run([str(target), "--json", "--rules", str(rules_file)]))

    assert capsys.readouterr().err.splitlines() == [
        _describe_deprecation("instructions", "question", rules_file)
    ]
    (request,) = judge.requests
    assert {
        question.question_id: question.question for question in request.questions
    } == {
        "first": "Is it first?",
        "second": "Is it second?",
        "both": "New?",
    }


def test_old_target_unit_types_field_still_picks_the_units_with_a_warning(
    tmp_path: Path,
    fake_judge: type[FakeJudge],
    capsys: pytest.CaptureFixture[str],
) -> None:
    rules_file = write_json(
        tmp_path / "rules.json",
        {
            "for_files": {
                "type": "choice",
                "question": "Is the file tidy?",
                "target_unit_types": ["file"],
            },
            "for_directories": {
                "type": "choice",
                "question": "Is the directory tidy?",
                "target_unit_types": ["project_directory"],
            },
        },
    )
    target = write_text(tmp_path / "a.py", "x = 1\n")
    judge = fake_judge()
    settings = make_settings(built_in_rule_packs=[], fallback_rule_packs=[])
    app = build_audit_command_app(FILE_AUDIT_COMMAND, judge, settings)

    asyncio.run(app.run([str(target), "--json", "--rules", str(rules_file)]))

    assert capsys.readouterr().err.splitlines() == [
        _describe_deprecation("target_unit_types", "unit_types", rules_file)
    ]
    assert judge.list_asked_rule_ids() == [["for_files"]]
