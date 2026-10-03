"""The audit-a-path use case: what is audited, reported and skipped."""

import asyncio
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import pytest

from src.app.usecases.audit_path import AuditPath, AuditPathResult
from src.app.wiring import create_file_audit_path, create_project_audit_path
from src.catalog.common.extractors.file_collector import collect_target_directories
from src.catalog.common.scales.pass_fail import PASS_FAIL_SCALE
from src.core.auditor import Auditor
from src.core.interfaces.extractor import BaseUnitExtractor
from src.core.interfaces.judge import BaseJudge
from src.core.models.unit import AuditableUnit
from src.infra.rule_loader.json_loader import JsonRuleLoader
from tests.helpers import (
    DEFAULT_PROJECT_RULES,
    DIR_RULE,
    FILE_RULE,
    UNIT_REGISTRY,
    Answers,
    FakeJudge,
    JudgeOverride,
    make_settings,
    write_json,
)

MOCK_PROJECT = Path("examples/mock_bad_project")
MOCK_DIRECTORIES = [
    str(MOCK_PROJECT),
    str(MOCK_PROJECT / "api"),
    str(MOCK_PROJECT / "domain"),
    str(MOCK_PROJECT / "utils"),
]


class RecordingListener:
    """Keeps what the use case reports, in the order it reports it."""

    def __init__(self) -> None:
        self.done: list[str] = []
        self.failed: list[tuple[str, str]] = []

    def target_failed(self, name: str, error: Exception) -> None:
        self.failed.append((name, str(error)))

    def target_done(self, name: str) -> None:
        self.done.append(name)


class PickyJudge(FakeJudge):
    """Fails on content that starts with ``refuses``; answers "fail" otherwise."""

    def __init__(self, refuses: str) -> None:
        super().__init__(default="fail")
        self.refuses = refuses

    async def answer(self, state: str, questions: Mapping[str, Any]) -> Answers:
        if state.startswith(self.refuses):
            raise RuntimeError("judge is down")
        return await super().answer(state, questions)


class CountingJudge(FakeJudge):
    """Records how many questions are being answered at the same time."""

    def __init__(self) -> None:
        super().__init__()
        self.running = 0
        self.most_at_once = 0

    async def answer(self, state: str, questions: Mapping[str, Any]) -> Answers:
        self.running += 1
        self.most_at_once = max(self.most_at_once, self.running)
        await asyncio.sleep(0)
        self.running -= 1
        return await super().answer(state, questions)


class BrokenExtractor(BaseUnitExtractor):
    async def extract(self, target: object) -> list[AuditableUnit]:
        raise OSError(f"cannot read {target}")


def _file_path(rules: Path, judge: BaseJudge) -> AuditPath:
    return create_file_audit_path(
        make_settings(rules_paths=(rules,)), JudgeOverride(judge)
    )


def _project_path(judge: BaseJudge, rules: Path = DEFAULT_PROJECT_RULES) -> AuditPath:
    return create_project_audit_path(
        make_settings(project_rules_paths=(rules,)), JudgeOverride(judge)
    )


def _run(
    audit_path: AuditPath,
    target: Path,
    listener: RecordingListener | None = None,
) -> AuditPathResult:
    async def prepare_and_run() -> AuditPathResult:
        plan = await audit_path.prepare(target)
        return await audit_path.run(plan, listener=listener)

    return asyncio.run(prepare_and_run())


@pytest.fixture
def rules(tmp_path: Path) -> Path:
    return write_json(tmp_path / "rules.json", {"tidy": FILE_RULE})


@pytest.fixture
def sources(tmp_path: Path) -> Path:
    directory = tmp_path / "src"
    directory.mkdir()
    for name in ("a.py", "b.py", "c.py"):
        (directory / name).write_text(f"# {name}\n", encoding="utf-8")
    return directory


# --- prepare ---------------------------------------------------------------


def test_prepare_lists_the_targets_and_loads_the_rules(
    rules: Path, sources: Path, fake_judge: type[FakeJudge]
) -> None:
    plan = asyncio.run(_file_path(rules, fake_judge()).prepare(sources))

    assert plan.root == sources
    assert plan.targets == [sources / "a.py", sources / "b.py", sources / "c.py"]
    assert [rule.rule_id for rule in plan.rules] == ["tidy"]


def test_prepare_adds_custom_rules(
    rules: Path, sources: Path, tmp_path: Path, fake_judge: type[FakeJudge]
) -> None:
    custom = write_json(tmp_path / "custom.json", {"house_rule": FILE_RULE})

    plan = asyncio.run(_file_path(rules, fake_judge()).prepare(sources, custom))

    assert sorted(rule.rule_id for rule in plan.rules) == ["house_rule", "tidy"]


def test_prepare_raises_before_anything_is_audited(
    rules: Path, sources: Path, tmp_path: Path, fake_judge: type[FakeJudge]
) -> None:
    judge = fake_judge()
    file_path = _file_path(rules, judge)

    with pytest.raises(FileNotFoundError, match="Audit target does not exist"):
        asyncio.run(file_path.prepare(tmp_path / "absent"))
    with pytest.raises(FileNotFoundError, match="Custom rules file does not exist"):
        asyncio.run(file_path.prepare(sources, tmp_path / "absent.json"))
    with pytest.raises(ValueError, match="must be a directory"):
        asyncio.run(_project_path(judge).prepare(sources / "a.py"))
    assert judge.calls == []


# --- one target at a time --------------------------------------------------


def test_every_target_is_audited_and_reported_done(
    rules: Path, sources: Path, fake_judge: type[FakeJudge]
) -> None:
    listener = RecordingListener()
    judge = fake_judge(default="fail")

    result = _run(_file_path(rules, judge), sources, listener)

    names = [str(sources / name) for name in ("a.py", "b.py", "c.py")]
    assert result.examined == names
    assert [finding.unit_id for finding in result.findings] == names
    assert sorted(listener.done) == names
    assert listener.failed == []


def test_run_without_a_listener_gives_the_same_result(
    rules: Path, sources: Path, fake_judge: type[FakeJudge]
) -> None:
    audit_path = _file_path(rules, fake_judge(default="fail"))

    assert _run(audit_path, sources) == _run(audit_path, sources, RecordingListener())


def test_a_target_that_fails_is_reported_and_left_out(
    rules: Path, sources: Path
) -> None:
    (sources / "b.py").write_text("poison\n", encoding="utf-8")
    listener = RecordingListener()

    result = _run(_file_path(rules, PickyJudge(refuses="poison")), sources, listener)

    kept = [str(sources / "a.py"), str(sources / "c.py")]
    assert result.examined == kept
    assert [finding.unit_id for finding in result.findings] == kept
    assert listener.failed == [(str(sources / "b.py"), "judge is down")]
    # A failed target still counts towards progress.
    assert len(listener.done) == 3


def test_selection_is_applied_to_the_findings(
    rules: Path, sources: Path, fake_judge: type[FakeJudge]
) -> None:
    audit_path = _file_path(rules, fake_judge(default="pass", confidence=0.4))

    async def run(fails_only: bool, min_confidence: float) -> int:
        plan = await audit_path.prepare(sources)
        result = await audit_path.run(plan, fails_only, min_confidence)
        return len(result.findings)

    assert asyncio.run(run(True, 0.0)) == 0
    assert asyncio.run(run(False, 0.0)) == 3
    assert asyncio.run(run(False, 0.5)) == 0


def test_no_more_than_the_limit_is_audited_at_once(rules: Path, tmp_path: Path) -> None:
    directory = tmp_path / "many"
    directory.mkdir()
    for index in range(20):
        (directory / f"m{index:02}.py").write_text("x = 1\n", encoding="utf-8")
    judge = CountingJudge()

    _run(_file_path(rules, judge), directory)

    assert 1 < judge.most_at_once <= 8


# --- whole tree ------------------------------------------------------------


@pytest.mark.usefixtures("in_repo_root")
def test_whole_tree_audits_each_directory_once(fake_judge: type[FakeJudge]) -> None:
    listener = RecordingListener()
    judge = fake_judge(default="fail")

    result = _run(_project_path(judge), MOCK_PROJECT, listener)

    assert result.examined == MOCK_DIRECTORIES
    assert [len(rule_ids) for rule_ids in judge.asked_rule_ids()] == [18] * 4
    assert len(result.findings) == 18 * 4
    # Findings come out a directory at a time, in the order of the targets.
    assert list(dict.fromkeys(f.unit_id for f in result.findings)) == MOCK_DIRECTORIES
    # Only the directories count towards progress, not the files inside them.
    assert sorted(listener.done) == MOCK_DIRECTORIES


@pytest.mark.usefixtures("in_repo_root")
def test_whole_tree_also_audits_nested_units_a_rule_targets(
    tmp_path: Path, fake_judge: type[FakeJudge]
) -> None:
    rules = write_json(
        tmp_path / "rules.json",
        {
            "for_dir": DIR_RULE,
            "for_file": {**FILE_RULE, "target_unit_types": ["file_metadata"]},
        },
    )
    judge = fake_judge()

    result = _run(_project_path(judge, rules), MOCK_PROJECT)

    asked = judge.asked_rule_ids()
    assert asked.count(["for_dir"]) == 4
    assert asked.count(["for_file"]) == len(asked) - 4 > 0
    assert result.examined == MOCK_DIRECTORIES


@pytest.mark.usefixtures("in_repo_root")
def test_whole_tree_leaves_out_a_directory_that_fails() -> None:
    judge = PickyJudge(refuses=f"Target Directory Under Audit: {MOCK_PROJECT / 'api'}")
    listener = RecordingListener()

    result = _run(_project_path(judge), MOCK_PROJECT, listener)

    assert result.examined == [d for d in MOCK_DIRECTORIES if not d.endswith("api")]
    assert listener.failed == [(str(MOCK_PROJECT / "api"), "judge is down")]
    assert sorted(listener.done) == MOCK_DIRECTORIES


@pytest.mark.usefixtures("in_repo_root")
def test_whole_tree_that_cannot_be_extracted_examines_nothing(
    fake_judge: type[FakeJudge],
) -> None:
    judge = fake_judge()
    auditor = Auditor(
        extractor=BrokenExtractor(),
        judge=judge,
        rule_loader=JsonRuleLoader([DEFAULT_PROJECT_RULES], UNIT_REGISTRY),
        scale=PASS_FAIL_SCALE,
    )
    audit_path = AuditPath(auditor, collect_target_directories, whole_tree=True)
    listener = RecordingListener()

    result = _run(audit_path, MOCK_PROJECT, listener)

    assert result == AuditPathResult(examined=[], findings=[])
    assert listener.failed == [(str(MOCK_PROJECT), f"cannot read {MOCK_PROJECT}")]
    assert listener.done == MOCK_DIRECTORIES
    assert judge.calls == []
