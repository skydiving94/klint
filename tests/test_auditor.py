"""The auditor: which rules reach the judge and what comes back."""

import asyncio
from pathlib import Path

import pytest

from tests.helpers import (
    DIR_RULE,
    FILE_RULE,
    FakeJudge,
    file_auditor,
    project_auditor,
    write_json,
)

MOCK_PROJECT = Path("examples/mock_bad_project")


def test_auditor_asks_only_rules_that_apply_to_the_unit(
    tmp_path: Path, fake_judge: type[FakeJudge]
) -> None:
    rules = write_json(
        tmp_path / "rules.json", {"for_file": FILE_RULE, "for_dir": DIR_RULE}
    )
    target = tmp_path / "a.py"
    target.write_text("x = 1\ny = 2\n", encoding="utf-8")
    judge = fake_judge(default="fail")

    report = asyncio.run(file_auditor(rules, judge).run_audit(target))

    assert judge.asked_rule_ids() == [["for_file"]]
    assert judge.calls[0][0] == "x = 1\ny = 2\n"
    (issue,) = report.get_issues()
    assert issue["rule_id"] == "for_file"
    assert issue["judgment"] == "Fail"
    assert issue["unit_id"] == issue["file_path"] == str(target)
    assert issue["line_range"] == [1, 2]


def test_auditor_does_not_call_the_judge_when_no_rule_applies(
    tmp_path: Path, fake_judge: type[FakeJudge]
) -> None:
    rules = write_json(tmp_path / "rules.json", {"for_dir": DIR_RULE})
    target = tmp_path / "a.py"
    target.write_text("x = 1\n", encoding="utf-8")
    judge = fake_judge()

    report = asyncio.run(file_auditor(rules, judge).run_audit(target))

    assert judge.calls == []
    assert report.get_issues(fails_only=False) == []


def test_auditor_skips_a_language_rule_for_a_unit_of_unknown_language(
    tmp_path: Path, fake_judge: type[FakeJudge]
) -> None:
    rules = write_json(
        tmp_path / "rules.json",
        {
            "any_language": FILE_RULE,
            "python_only": {**FILE_RULE, "languages": ["python"]},
        },
    )
    target = tmp_path / "a.py"
    target.write_text("x = 1\n", encoding="utf-8")
    judge = fake_judge()

    asyncio.run(file_auditor(rules, judge).run_audit(target))

    # The extracted unit has no language, so the Python-only rule is not asked.
    assert judge.asked_rule_ids() == [["any_language"]]


# --- nested units ----------------------------------------------------------


@pytest.mark.usefixtures("in_repo_root")
def test_extract_units_returns_only_the_top_units_by_default(
    tmp_path: Path, fake_judge: type[FakeJudge]
) -> None:
    rules = write_json(tmp_path / "rules.json", {"for_dir": DIR_RULE})
    auditor = project_auditor(rules, fake_judge())

    units = asyncio.run(auditor.extract_units(MOCK_PROJECT))

    assert [unit.unit_id for unit in units] == [str(MOCK_PROJECT)]


@pytest.mark.usefixtures("in_repo_root")
def test_extract_units_can_walk_children_parents_first(
    tmp_path: Path, fake_judge: type[FakeJudge]
) -> None:
    rules = write_json(tmp_path / "rules.json", {"for_dir": DIR_RULE})
    auditor = project_auditor(rules, fake_judge())

    units = asyncio.run(auditor.extract_units(MOCK_PROJECT, walk_children=True))

    directories = [u.unit_id for u in units if u.unit_type == "project_directory"]
    assert directories == [
        str(MOCK_PROJECT),
        str(MOCK_PROJECT / "api"),
        str(MOCK_PROJECT / "domain"),
        str(MOCK_PROJECT / "utils"),
    ]
    # Each directory is followed by its own files, before the next directory.
    api_index = units.index(next(u for u in units if u.unit_id.endswith("api")))
    assert units[api_index + 1].unit_type == "file_metadata"


@pytest.mark.usefixtures("in_repo_root")
def test_run_audit_with_children_audits_every_unit_a_rule_applies_to(
    tmp_path: Path, fake_judge: type[FakeJudge]
) -> None:
    rules = write_json(tmp_path / "rules.json", {"for_dir": DIR_RULE})
    judge = fake_judge(default="fail")
    auditor = project_auditor(rules, judge)

    top_only = asyncio.run(auditor.run_audit(MOCK_PROJECT))
    whole_tree = asyncio.run(auditor.run_audit(MOCK_PROJECT, walk_children=True))

    assert len(top_only.get_issues()) == 1
    # Four directories; the files inside them match no rule and are not asked.
    assert len(whole_tree.get_issues()) == 4
    assert len(judge.calls) == 1 + 4
