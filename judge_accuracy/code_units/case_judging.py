"""Asking the judge about every true and planted unit of a case module."""

import sys
from dataclasses import dataclass
from pathlib import Path

from judge_accuracy.code_units.case_set import CaseModule, PlantedProblem
from judge_accuracy.code_units.judged_unit import CodeUnitType, JudgedUnit
from judge_accuracy.code_units.module_prefixes import (
    choose_prefix_end_lines,
    cut_to_line,
)
from klint.app.pipeline import AuditPipeline, AuditRequest
from klint.core.interfaces import AuditKind, BaseAuditProgressListener
from klint.core.models.audits import DiskPathInput, RenderInput
from klint.core.models.reports import AuditFinding

# Each module is judged under this folder, so that its file is tagged as
# backend code whatever it imports, and every backend rule is asked.
_BACKEND_FOLDER_NAME = "api"


class _RefusalListener(BaseAuditProgressListener):
    """Prints a line on stderr for each unit the judge refuses."""

    def __init__(self, line_prefix: str) -> None:
        self._line_prefix = line_prefix

    def report_audit_started(self, unit_count: int) -> None:
        del unit_count

    def report_unit_audited(self, unit_id: str) -> None:
        del unit_id

    def report_unit_failed(self, unit_id: str, error: Exception) -> None:
        print(f"{self._line_prefix} Refused {unit_id}: {error}", file=sys.stderr)


@dataclass(frozen=True)
class _DocumentUnit:
    """One unit of a judged module: its text shown whole, and its findings.

    findings is None when the judge refused to answer about it.
    """

    unit_type: CodeUnitType
    subject: str
    findings: tuple[AuditFinding, ...] | None


class CaseModuleJudging:
    """Judges a case module, cut to a prefix for each band of length.

    Every unit of each true prefix is a true case. Each planted problem is
    planted in each prefix that holds its text, and every unit whose text
    the problem changes, and that is asked the rule it breaks, is a planted
    case. A unit judged twice with the same text counts once.
    """

    def __init__(
        self,
        audit_pipeline: AuditPipeline,
        audit_kind: AuditKind,
        work_folder: Path,
        line_prefix: str,
    ) -> None:
        self._audit_pipeline = audit_pipeline
        self._audit_kind = audit_kind
        self._work_folder = work_folder
        self._listener = _RefusalListener(line_prefix)

    async def judge_case_module(self, case_module: CaseModule) -> list[JudgedUnit]:
        """Return each true and planted unit of ``case_module`` and its findings."""
        judged: dict[tuple[int | None, CodeUnitType, str], JudgedUnit] = {}
        source = case_module.true_source
        for end_line in choose_prefix_end_lines(source):
            true_prefix = cut_to_line(source, end_line)
            true_units = await self._judge_module(case_module.name, true_prefix)
            for unit_name, unit in true_units.items():
                judged.setdefault(
                    (None, unit.unit_type, unit.subject),
                    _build_judged_unit(case_module.name, unit_name, unit),
                )
            for number, problem in enumerate(case_module.planted_problems, start=1):
                if problem.old_text not in true_prefix:
                    continue
                planted_prefix = true_prefix.replace(
                    problem.old_text, problem.new_text, 1
                )
                planted_units = await self._judge_module(
                    case_module.name, planted_prefix
                )
                for unit_name, unit in planted_units.items():
                    true_unit = true_units.get(unit_name)
                    if not _is_planted_case(unit, true_unit, problem):
                        continue
                    judged.setdefault(
                        (number, unit.unit_type, unit.subject),
                        _build_judged_unit(
                            case_module.name, unit_name, unit, problem, number
                        ),
                    )
        return list(judged.values())

    async def _judge_module(self, name: str, source: str) -> dict[str, _DocumentUnit]:
        """Judge ``source`` as the file ``name``.py; return its units by name."""
        path = self._work_folder / _BACKEND_FOLDER_NAME / f"{name}.py"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(source, encoding="utf-8")
        audit_input = DiskPathInput(path=path)
        outcome = await self._audit_pipeline.run_audit(
            AuditRequest(
                audit_input=audit_input,
                audit_kind_id=self._audit_kind.kind_id,
                audit_progress_listener=self._listener,
            )
        )
        acquired = await self._audit_kind.unit_source.read_units(audit_input)
        audited_unit_ids = set(outcome.report.list_audited_unit_ids())
        unit_name_to_unit: dict[str, _DocumentUnit] = {}
        for unit in acquired.units:
            if unit.unit_id not in outcome.selected_unit_ids:
                continue
            renderer = self._audit_kind.find_renderer(unit)
            subject = renderer.render_subject(
                RenderInput(
                    unit=unit, character_budget=self._audit_kind.character_budget
                )
            )
            unit_name = unit.unit_id.replace(str(path), path.name, 1)
            unit_name_to_unit[unit_name] = _DocumentUnit(
                unit_type=CodeUnitType(unit.unit_type),
                subject=subject,
                findings=(
                    tuple(
                        finding
                        for finding in outcome.report.list_findings()
                        if finding.unit_id == unit.unit_id
                    )
                    if unit.unit_id in audited_unit_ids
                    else None
                ),
            )
        return unit_name_to_unit


def _is_planted_case(
    unit: _DocumentUnit, true_unit: _DocumentUnit | None, problem: PlantedProblem
) -> bool:
    """Return True when ``problem`` changed ``unit`` and its rule is asked of it.

    A unit the judge refused is asked what its true version was asked.
    """
    if true_unit is not None and true_unit.subject == unit.subject:
        return False
    asked_findings = unit.findings
    if asked_findings is None and true_unit is not None:
        asked_findings = true_unit.findings
    return any(finding.rule_id == problem.rule_id for finding in asked_findings or ())


def _build_judged_unit(
    case_module_name: str,
    unit_name: str,
    unit: _DocumentUnit,
    planted_problem: PlantedProblem | None = None,
    planted_number: int | None = None,
) -> JudgedUnit:
    return JudgedUnit(
        case_module_name=case_module_name,
        unit_name=unit_name,
        unit_type=unit.unit_type,
        length=len(unit.subject),
        findings=unit.findings,
        planted_problem=planted_problem,
        planted_number=planted_number,
    )
