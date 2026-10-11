"""The auditor: which rules reach the judge and what comes back."""

import asyncio
from pathlib import Path

import pytest

from src.catalog.common.scales.pass_fail import PASS_FAIL_SCALE
from src.core.interfaces.judge import BaseJudge
from src.core.models.location import Location
from src.core.models.report import AuditFinding
from src.core.models.scale import Choice
from tests.support.builders import (
    DIR_RULE,
    FAIL,
    FILE_RULE,
    IRRELEVANT,
    LACK_OF_EVIDENCE,
    PASS,
    file_auditor,
    project_auditor,
    write_json,
    write_text,
)
from tests.support.fakes import FakeJudge
from tests.support.paths import DEFAULT_PROJECT_RULES, MOCK_PROJECT

RULES = {
    "first": {"type": "choice", "instructions": "Is the first thing done?"},
    "second": {"type": "choice", "instructions": "Is the second thing done?"},
}


@pytest.fixture
def target(tmp_path: Path) -> Path:
    path = tmp_path / "a.py"
    path.write_text("x = 1\n", encoding="utf-8")
    return path


def _findings(judge: BaseJudge, target: Path) -> list[AuditFinding]:
    """Audit ``target`` against RULES and return every finding."""
    rules_path = write_json(target.parent / "rules.json", RULES)
    auditor = file_auditor(rules_path, judge)
    return asyncio.run(auditor.run_audit(target)).get_findings(fails_only=False)


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


@pytest.mark.parametrize(
    ("file_name", "asked"),
    [
        ("a.py", ["any_language", "python_only"]),
        ("a.go", ["any_language"]),
        ("notes.txt", ["any_language"]),
    ],
)
def test_auditor_asks_a_language_rule_only_about_files_in_that_language(
    tmp_path: Path, fake_judge: type[FakeJudge], file_name: str, asked: list[str]
) -> None:
    rules = write_json(
        tmp_path / "rules.json",
        {
            "any_language": FILE_RULE,
            "python_only": {**FILE_RULE, "languages": ["python"]},
        },
    )
    target = tmp_path / file_name
    target.write_text("x = 1\n", encoding="utf-8")
    judge = fake_judge()

    asyncio.run(file_auditor(rules, judge).run_audit(target))

    # A file in another language, or in none that is known, is not asked.
    assert judge.asked_rule_ids() == [asked]


def test_project_audit_asks_a_language_rule_only_about_files_in_that_language(
    tmp_path: Path, fake_judge: type[FakeJudge]
) -> None:
    python_only = {
        **FILE_RULE,
        "target_unit_types": ["file_metadata"],
        "languages": ["python"],
    }
    rules = write_json(tmp_path / "rules.json", {"python_only": python_only})
    for name in ("a.py", "b.java", "c.txt"):
        write_text(tmp_path / "pkg" / name, "x = 1\n")
    judge = fake_judge()
    auditor = project_auditor(rules, judge)

    asyncio.run(auditor.run_audit(tmp_path / "pkg", walk_children=True))

    (asked_about,) = [state for state, _ in judge.calls]
    assert asked_about.startswith("a.py ")


def test_python_project_rules_are_asked_only_about_directories_holding_python(
    tmp_path: Path, fake_judge: type[FakeJudge]
) -> None:
    repo = tmp_path / "repo"
    write_text(repo / "app" / "main.py", "x = 1\n")
    write_text(repo / "docs" / "intro.md", "# Intro\n")
    auditor = project_auditor(DEFAULT_PROJECT_RULES, fake_judge())

    report = asyncio.run(auditor.run_audit(repo, walk_children=True))

    judged = {finding.unit_id for finding in report.get_findings(fails_only=False)}
    assert judged == {str(repo), str(repo / "app")}


def test_unit_content_is_sent_as_state_with_one_question_per_rule(
    fake_judge: type[FakeJudge], target: Path
) -> None:
    judge = fake_judge()

    _findings(judge, target)

    ((state, questions),) = judge.calls
    assert state == "x = 1\n"
    assert questions == {
        rule_id: {
            "type": "choice",
            "instructions": spec["instructions"],
            "criteria": PASS_FAIL_SCALE.criteria_payload(),
        }
        for rule_id, spec in RULES.items()
    }


@pytest.mark.parametrize(
    ("key", "choice"),
    [
        ("pass", PASS),
        ("fail", FAIL),
        ("irrelevant", IRRELEVANT),
        ("lack_of_evidence", LACK_OF_EVIDENCE),
    ],
)
def test_each_answer_maps_to_its_choice(
    fake_judge: type[FakeJudge], target: Path, key: str, choice: Choice
) -> None:
    findings = _findings(fake_judge(default=key), target)
    assert [f.choice for f in findings] == [choice, choice]


def test_finding_carries_the_answer_and_the_unit_location(
    fake_judge: type[FakeJudge], target: Path
) -> None:
    judge = fake_judge(choices={"first": "fail"}, confidence=0.75)

    first, second = _findings(judge, target)

    assert first == AuditFinding(
        rule_id="first",
        unit_id=str(target),
        choice=FAIL,
        instructions="Is the first thing done?",
        confidence=0.75,
        probabilities={"fail": 0.75},
        location=Location(str(target), 1, 1),
        metadata={"file_path": str(target), "line_range": [1, 1]},
    )
    assert second.rule_id == "second"
    assert second.choice is PASS


def test_rule_without_an_answer_produces_no_finding(
    fake_judge: type[FakeJudge], target: Path
) -> None:
    findings = _findings(fake_judge(choices={"first": None}), target)
    assert [f.rule_id for f in findings] == ["second"]


def test_unknown_answer_raises_key_error(
    fake_judge: type[FakeJudge], target: Path
) -> None:
    with pytest.raises(KeyError, match="maybe"):
        _findings(fake_judge(default="maybe"), target)


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
