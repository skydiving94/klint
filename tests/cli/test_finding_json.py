"""The JSON form of a finding: one fixed set of keys, whatever the unit."""

import asyncio
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest
from injector import Binder

from klint.catalog.domain_neutral.extraction.dispatched_file import DispatchedFile
from klint.catalog.domain_neutral.units.file import AuditableFileUnit
from klint.cli.file_audit import FILE_AUDIT_COMMAND
from klint.cli.runner import AuditCommandApp
from klint.cli.structure_audit import STRUCTURE_AUDIT_COMMAND
from klint.core.interfaces.extractor import BaseUnitExtractor
from klint.core.models.unit import AuditableUnit, UnitContext
from tests.support.builders import (
    DIR_RULE,
    FILE_RULE,
    build_audit_command_app,
    make_settings,
    write_json,
    write_text,
)
from tests.support.fakes import FakeJudge

Capture = pytest.CaptureFixture[str]

FINDING_KEYS = [
    "rule_id",
    "unit_id",
    "answer",
    "confidence",
    "choice_key_to_probability",
    "question",
    "tags",
    "location",
    "evidence_location",
    "context",
]


@dataclass(frozen=True)
class RuleIdContext(UnitContext):
    """A context with a field named like a field of the finding."""

    rule_id: str


@dataclass(frozen=True)
class SpoofingFileUnit(AuditableFileUnit):
    """A whole file whose context claims a rule ID of its own."""

    def get_context(self) -> RuleIdContext:
        return RuleIdContext(rule_id="spoofed")


class SpoofingExtractor(BaseUnitExtractor[DispatchedFile]):
    async def extract(self, audit_input: DispatchedFile) -> list[AuditableUnit]:
        path = audit_input.path
        return [SpoofingFileUnit(unit_id=str(path), content=path.read_text())]


def use_the_spoofing_extractor_for_python(binder: Binder) -> None:
    binder.multibind(
        dict[str, BaseUnitExtractor[DispatchedFile]], to={"python": SpoofingExtractor}
    )


def _run_findings(
    app: AuditCommandApp, target: Path, capsys: Capture
) -> list[dict[str, Any]]:
    asyncio.run(app.run([str(target), "--json", "--all-answers"]))
    findings: list[dict[str, Any]] = json.loads(capsys.readouterr().out)["findings"]
    return findings


def test_findings_on_files_directories_and_file_metadata_share_their_keys(
    tmp_path: Path, fake_judge: type[FakeJudge], capsys: Capture
) -> None:
    project = tmp_path / "project"
    write_text(project / "pkg" / "a.py", "x = 1\n")
    rules = write_json(
        tmp_path / "rules.json",
        {
            "directory_rule": DIR_RULE,
            "file_metadata_rule": {**FILE_RULE, "target_unit_types": ["file_metadata"]},
            "file_rule": FILE_RULE,
        },
    )
    settings = make_settings(built_in_rule_packs=[rules], fallback_rule_packs=[rules])
    file_app = build_audit_command_app(FILE_AUDIT_COMMAND, fake_judge(), settings)
    structure_app = build_audit_command_app(
        STRUCTURE_AUDIT_COMMAND, fake_judge(), settings
    )

    findings = [
        *_run_findings(file_app, project, capsys),
        *_run_findings(structure_app, project, capsys),
    ]

    rule_id_to_keys = {finding["rule_id"]: list(finding) for finding in findings}
    assert rule_id_to_keys == {
        "file_rule": FINDING_KEYS,
        "directory_rule": FINDING_KEYS,
        "file_metadata_rule": FINDING_KEYS,
    }


def test_unit_context_with_a_rule_id_leaves_the_finding_rule_id_unchanged(
    tmp_path: Path, fake_judge: type[FakeJudge], capsys: Capture
) -> None:
    target = write_text(tmp_path / "a.py", "x = 1\n")
    app = build_audit_command_app(
        FILE_AUDIT_COMMAND,
        fake_judge(),
        overrides=[use_the_spoofing_extractor_for_python],
    )

    (finding,) = _run_findings(app, target, capsys)

    assert finding["rule_id"] == "tidy_file"
    assert finding["context"] == {"rule_id": "spoofed"}
