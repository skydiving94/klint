"""Asking the judge about every labelled summary of a case file."""

import json
import sys
from collections.abc import Sequence

from judge_accuracy.change_summary.case_set import CaseFile, MistakeKind
from judge_accuracy.change_summary.judged_summary import JudgedSummary
from klint.app.pipeline import AuditOutcome, AuditPipeline, AuditRequest
from klint.catalog.change_summary import CHANGE_SUMMARY_KIND_ID
from klint.catalog.change_summary.units.summary_context import ChangeSummaryContext
from klint.core.interfaces import AuditKind, BaseAuditProgressListener
from klint.core.models.audits import InMemoryBytesInput, RenderInput
from klint.core.models.reports import JsonValue
from klint.core.models.units import AuditableUnit

_JSON_MEDIA_TYPE = "application/json"
# A budget no premise reaches, to render a unit's whole evidence.
_UNLIMITED_CHARACTER_BUDGET = 10**9


class _RefusalListener(BaseAuditProgressListener):
    """Prints a line on stderr for each summary the judge refuses."""

    def __init__(self, line_prefix: str) -> None:
        self._line_prefix = line_prefix

    def report_audit_started(self, unit_count: int) -> None:
        del unit_count

    def report_unit_audited(self, unit_id: str) -> None:
        del unit_id

    def report_unit_failed(self, unit_id: str, error: Exception) -> None:
        print(f"{self._line_prefix} Refused {unit_id}: {error}", file=sys.stderr)


class CaseFileJudging:
    """Audits a case file's true document, then each of its planted documents.

    Every summary of the true document is a true case; each planted mistake
    is a case of its own, judged in the document it is planted in.
    """

    def __init__(
        self, audit_pipeline: AuditPipeline, audit_kind: AuditKind, line_prefix: str
    ) -> None:
        if audit_kind.kind_id != CHANGE_SUMMARY_KIND_ID:
            raise ValueError(f"Expected the {CHANGE_SUMMARY_KIND_ID} kind of audit")
        self._audit_pipeline = audit_pipeline
        self._audit_kind = audit_kind
        self._listener = _RefusalListener(line_prefix)

    async def judge_case_file(self, case_file: CaseFile) -> list[JudgedSummary]:
        """Return each labelled summary of ``case_file`` and what the judge found.

        Raises OSError or ValueError when a document cannot be read.
        """
        true_units = await self._read_units(case_file.true_document)
        true_outcome = await self._audit(case_file.true_document)
        judged = [
            self._build_judged_summary(case_file.name, unit, None, true_outcome)
            for unit in true_units
            if unit.get_location() is not None
        ]
        for mistake in case_file.planted_mistakes:
            document = case_file.build_planted_document(mistake)
            unit = _find_unit_at(
                await self._read_units(document), mistake.summary_pointer
            )
            outcome = await self._audit(document)
            judged.append(
                self._build_judged_summary(
                    case_file.name, unit, mistake.mistake_kind, outcome
                )
            )
        return judged

    async def _read_units(self, document: JsonValue) -> list[AuditableUnit]:
        acquired = await self._audit_kind.unit_source.read_units(_build_input(document))
        return acquired.units

    async def _audit(self, document: JsonValue) -> AuditOutcome:
        return await self._audit_pipeline.run_audit(
            AuditRequest(
                audit_input=_build_input(document),
                audit_kind_id=self._audit_kind.kind_id,
                audit_progress_listener=self._listener,
            )
        )

    def _build_judged_summary(
        self,
        case_file_name: str,
        unit: AuditableUnit,
        mistake_kind: MistakeKind | None,
        outcome: AuditOutcome,
    ) -> JudgedSummary:
        report = outcome.report
        context = unit.get_context()
        if not isinstance(context, ChangeSummaryContext):
            raise TypeError(f"{unit.unit_id} is not a change summary")
        is_refused = unit.unit_id not in report.list_audited_unit_ids()
        return JudgedSummary(
            case_file_name=case_file_name,
            unit_id=unit.unit_id,
            level=context.level,
            is_over_cut=self._is_over_cut(unit),
            mistake_kind=mistake_kind,
            findings=None
            if is_refused
            else tuple(
                finding
                for finding in report.list_findings()
                if finding.unit_id == unit.unit_id
            ),
        )

    def _is_over_cut(self, unit: AuditableUnit) -> bool:
        """Return True when the text about ``unit`` is cut to fit the budget."""
        renderer = self._audit_kind.find_renderer(unit)
        within_budget = renderer.render_subject(
            RenderInput(unit=unit, character_budget=self._audit_kind.character_budget)
        )
        whole = renderer.render_subject(
            RenderInput(unit=unit, character_budget=_UNLIMITED_CHARACTER_BUDGET)
        )
        return within_budget != whole


def _build_input(document: JsonValue) -> InMemoryBytesInput:
    return InMemoryBytesInput(
        content=json.dumps(document).encode("utf-8"), media_type=_JSON_MEDIA_TYPE
    )


def _find_unit_at(units: Sequence[AuditableUnit], pointer: str) -> AuditableUnit:
    """Return the unit whose summary sits at ``pointer``."""
    for unit in units:
        location = unit.get_location()
        if location is not None and location.path == pointer:
            return unit
    raise ValueError(f"No summary of the document sits at {pointer}")
