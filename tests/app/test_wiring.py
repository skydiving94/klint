"""The object graph klint builds from its settings."""

import asyncio
import sys
from pathlib import Path
from types import ModuleType

import pytest

from src.app.wiring import (
    FileAuditor,
    FileAuditPath,
    ProjectAuditor,
    ProjectAuditPath,
    create_file_audit_path,
    create_injector,
    create_project_audit_path,
)
from src.core.interfaces.judge import BaseJudge
from src.core.registry import UnitRegistry
from src.infra.system_one.remote import RemoteSystemOneJudge
from tests.support.builders import FILE_RULE, make_settings, write_json
from tests.support.fakes import FakeJudge, JudgeOverride

LOCAL_MODULE = "src.infra.system_one.local"


class StubLocalJudge(FakeJudge):
    """Stands in for the in-process judge, which needs the model runtime."""

    def __init__(self, checkpoint: str) -> None:
        super().__init__()
        self.checkpoint = checkpoint


@pytest.fixture
def local_module(monkeypatch: pytest.MonkeyPatch) -> ModuleType:
    module = ModuleType(LOCAL_MODULE)
    module.__dict__["LocalKevJudge"] = StubLocalJudge
    monkeypatch.setitem(sys.modules, LOCAL_MODULE, module)
    return module


def _judge(kev_mode: str) -> BaseJudge:
    injector = create_injector(make_settings(kev_mode=kev_mode))
    judge = injector.get(BaseJudge)  # type: ignore[type-abstract]
    assert isinstance(judge, BaseJudge)
    return judge


@pytest.mark.parametrize("kev_mode", ["remote", "anything-else"])
def test_any_mode_but_local_gives_the_remote_judge(kev_mode: str) -> None:
    assert isinstance(_judge(kev_mode), RemoteSystemOneJudge)


@pytest.mark.usefixtures("local_module")
def test_local_mode_gives_the_in_process_judge_for_the_configured_model() -> None:
    judge = _judge("local")

    assert isinstance(judge, StubLocalJudge)
    assert judge.checkpoint == "fake"


def test_remote_mode_does_not_import_the_local_runtime(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delitem(sys.modules, LOCAL_MODULE, raising=False)

    _judge("remote")

    assert LOCAL_MODULE not in sys.modules


def test_everything_is_built_once_per_injector() -> None:
    injector = create_injector(make_settings())

    assert injector.get(FileAuditPath) is injector.get(FileAuditPath)
    assert injector.get(ProjectAuditPath) is injector.get(ProjectAuditPath)
    assert injector.get(FileAuditor) is injector.get(FileAuditor)
    assert injector.get(ProjectAuditor) is injector.get(ProjectAuditor)
    assert injector.get(UnitRegistry) is injector.get(UnitRegistry)
    assert injector.get(FileAuditPath) is not create_file_audit_path(make_settings())


def test_registry_holds_the_unit_types_of_the_built_in_suites() -> None:
    registry = create_injector(make_settings()).get(UnitRegistry)

    assert registry.known_unit_types() == ["file", "file_metadata", "project_directory"]


def test_both_auditors_share_the_overridden_judge(
    tmp_path: Path, fake_judge: type[FakeJudge]
) -> None:
    file_rules = write_json(tmp_path / "file.json", {"tidy": FILE_RULE})
    target = tmp_path / "pkg"
    target.mkdir()
    (target / "a.py").write_text("x = 1\n", encoding="utf-8")
    judge = fake_judge()
    injector = create_injector(
        make_settings(rules_paths=(file_rules,)), JudgeOverride(judge)
    )

    asyncio.run(injector.get(FileAuditor).run_audit(target / "a.py"))
    asyncio.run(injector.get(ProjectAuditor).run_audit(target))

    assert [len(rule_ids) for rule_ids in judge.asked_rule_ids()] == [1, 18]


def test_project_audit_needs_project_rule_packs() -> None:
    settings = make_settings(project_rules_paths=())

    with pytest.raises(EnvironmentError, match="KEV_DEFAULT_PROJECT_RULES_PATH"):
        create_project_audit_path(settings)
    # The file audit does not depend on them.
    create_file_audit_path(settings)
