import asyncio
from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass, replace

from klint.core.interfaces import (
    AuditKind,
    BaseAuditProgressListener,
    BaseJudge,
    BaseUnitRenderer,
)
from klint.core.models.audits import AuditOrder, RenderInput
from klint.core.models.judging import (
    AnswerScale,
    JudgeAnswer,
    JudgeQuestion,
    JudgeRequest,
    JudgeUsage,
)
from klint.core.models.reports import AuditFinding, AuditReport
from klint.core.models.rules import AuditRule, RuleSet
from klint.core.models.units import (
    AuditableUnit,
    list_ancestor_unit_ids,
    map_unit_id_to_parent_unit_id,
)

# The most units audited at the same time.
_MAX_CONCURRENT_AUDITS = 8
# A budget no unit's text reaches, to render the whole of it.
_WHOLE_TEXT_CHARACTER_BUDGET = 10**12


@dataclass(frozen=True)
class _UnitAudit:
    """The findings on one unit, and the judge's usage in finding them."""

    findings: list[AuditFinding]
    judge_usage: JudgeUsage


class Auditor:
    """Audits units and reports what the judge finds.

    Asks the judge the rules a rule set chooses for each unit, about the
    text the unit's renderer writes, a limited number of units at a time,
    in the order the audit asks for, and turns the answers into findings.
    A rule whose answer the renderer knows is not asked. A unit whose audit
    fails is left out and the others go on. The report adds up the judge's
    usage over the units audited.
    """

    def __init__(self, judge: BaseJudge) -> None:
        self._judge = judge

    async def audit(
        self,
        units: Sequence[AuditableUnit],
        rule_set: RuleSet,
        audit_kind: AuditKind,
        audit_progress_listener: BaseAuditProgressListener | None = None,
    ) -> AuditReport:
        """Audit each unit with the rules ``rule_set`` chooses; return the report.

        The judge reads about each unit the text its renderer in
        ``audit_kind`` writes, within the kind's character budget, and
        answers on the kind's scale. In the kind's CHILDREN_FIRST order, the
        units are judged a level at a time, the deepest first, so that each
        is judged after the units nested inside it, and its renderer is given
        their findings; the limit on units judged at once applies within a
        level. Whatever the order, the report
        holds the units audited without error, and their findings, in the
        order of ``units``. The listener, when given, is told when the audit
        starts and about each unit as its audit ends. Raises ValueError,
        before the judge is asked, when the kind has no renderer for a unit.
        """
        renderers = [audit_kind.find_renderer(unit) for unit in units]
        if audit_progress_listener is not None:
            audit_progress_listener.report_audit_started(len(units))
        semaphore = asyncio.Semaphore(_MAX_CONCURRENT_AUDITS)

        unit_findings: list[list[AuditFinding] | None] = [None] * len(units)
        # Where each unit sits in ``units``, found by the unit itself, so that
        # units sharing an ID keep their findings apart.
        unit_identity_to_index = {id(unit): index for index, unit in enumerate(units)}

        def collect_child_findings(unit: AuditableUnit) -> tuple[AuditFinding, ...]:
            """Return the findings so far on the units nested directly in ``unit``."""
            child_findings: list[AuditFinding] = []
            for child in unit.list_children():
                index = unit_identity_to_index.get(id(child))
                if index is not None:
                    child_findings.extend(unit_findings[index] or ())
            return tuple(child_findings)

        async def audit_one(index: int) -> _UnitAudit | None:
            """Return the audit of ``units[index]``; None when it fails."""
            unit = units[index]
            render_input = RenderInput(
                unit=unit,
                character_budget=audit_kind.character_budget,
                child_findings=collect_child_findings(unit),
            )
            async with semaphore:
                try:
                    unit_audit = await self._audit_unit(
                        render_input,
                        renderers[index],
                        rule_set.select_rules_for(unit),
                        audit_kind.answer_scale,
                    )
                except Exception as error:
                    # Whatever went wrong, such as the judge not answering,
                    # only this unit is left out.
                    if audit_progress_listener is not None:
                        audit_progress_listener.report_unit_failed(unit.unit_id, error)
                    return None
            if audit_progress_listener is not None:
                audit_progress_listener.report_unit_audited(unit.unit_id)
            return unit_audit

        # A level's findings are recorded once the whole level is judged, so
        # what a renderer is given does not depend on timing.
        report = AuditReport()
        for level in _order_levels(units, audit_kind.audit_order):
            level_audits = await asyncio.gather(*(audit_one(index) for index in level))
            for index, unit_audit in zip(level, level_audits, strict=True):
                if unit_audit is None:
                    continue
                unit_findings[index] = unit_audit.findings
                report.record_judge_usage(unit_audit.judge_usage)
        for unit, findings in zip(units, unit_findings, strict=True):
            if findings is None:
                continue
            report.record_audited_unit(unit.unit_id)
            for finding in findings:
                report.record(finding)
        return report

    async def _audit_unit(
        self,
        render_input: RenderInput,
        renderer: BaseUnitRenderer,
        rules: Sequence[AuditRule],
        answer_scale: AnswerScale,
    ) -> _UnitAudit:
        """Answer ``rules`` about one unit.

        The renderer's known answers come first, with no confidence: the
        judge did not give them. The judge is asked the other rules, and is
        not called when none is left. A finding the judge gave on a text cut
        to the budget names the budget.
        """
        judge_usage = JudgeUsage()
        if not rules:
            return _UnitAudit(findings=[], judge_usage=judge_usage)
        unit = render_input.unit
        rule_id_to_known_choice_key = renderer.find_known_answers(
            render_input, [rule.rule_id for rule in rules]
        )
        question_id_to_answer = {
            rule_id: JudgeAnswer(question_id=rule_id, choice_key=choice_key)
            for rule_id, choice_key in rule_id_to_known_choice_key.items()
            if choice_key is not None
        }
        asked_rules = [
            rule for rule in rules if rule.rule_id not in rule_id_to_known_choice_key
        ]
        cut_at_characters: int | None = None
        if asked_rules:
            subject = renderer.render_subject(render_input)
            if subject != renderer.render_subject(
                replace(render_input, character_budget=_WHOLE_TEXT_CHARACTER_BUDGET)
            ):
                cut_at_characters = render_input.character_budget
            request = _build_request(subject, unit.unit_type, asked_rules, answer_scale)
            reply = await self._judge.answer(request)
            judge_usage = reply.usage
            for judge_answer in reply.answers:
                question_id_to_answer.setdefault(judge_answer.question_id, judge_answer)
        findings: list[AuditFinding] = []
        for rule in rules:
            answer = question_id_to_answer.get(rule.rule_id)
            if answer is None:
                continue
            findings.append(
                AuditFinding(
                    rule_id=rule.rule_id,
                    unit_id=unit.unit_id,
                    answer=answer_scale.find_choice(answer.choice_key),
                    question=rule.find_question(unit.unit_type),
                    confidence=answer.confidence,
                    choice_key_to_probability=answer.choice_key_to_probability,
                    tags=tuple(rule.tags),
                    location=unit.get_location(),
                    evidence_location=unit.get_evidence_location(),
                    context=unit.get_context(),
                    cut_at_characters=(
                        None
                        if rule.rule_id in rule_id_to_known_choice_key
                        else cut_at_characters
                    ),
                )
            )
        return _UnitAudit(findings=findings, judge_usage=judge_usage)


def _order_levels(
    units: Sequence[AuditableUnit], audit_order: AuditOrder
) -> list[list[int]]:
    """Return the positions in ``units`` of the groups to judge one by one.

    The units of a group are judged together. With CHILDREN_FIRST, a group
    holds the units at one depth of nesting, the deepest group first.
    """
    match audit_order:
        case AuditOrder.ALL_AT_ONCE:
            return [list(range(len(units)))]
        case AuditOrder.CHILDREN_FIRST:
            unit_id_to_parent_unit_id = map_unit_id_to_parent_unit_id(units)
            depth_to_indexes: defaultdict[int, list[int]] = defaultdict(list)
            for index, unit in enumerate(units):
                depth = len(
                    list_ancestor_unit_ids(unit.unit_id, unit_id_to_parent_unit_id)
                )
                depth_to_indexes[depth].append(index)
            return [depth_to_indexes[depth] for depth in sorted(depth_to_indexes)[::-1]]


def _build_request(
    subject: str,
    unit_type: str,
    rules: Sequence[AuditRule],
    answer_scale: AnswerScale,
) -> JudgeRequest:
    """Return the request that asks each rule about ``subject``, by rule id.

    ``subject`` is about a unit of type ``unit_type``; each rule is asked its
    question for that type.
    """
    choice_key_to_criterion = answer_scale.map_choice_key_to_criterion()
    return JudgeRequest(
        subject=subject,
        questions=tuple(
            JudgeQuestion(
                question_id=rule.rule_id,
                question_type=rule.question_type,
                question=rule.find_question(unit_type),
                choice_key_to_criterion=choice_key_to_criterion,
            )
            for rule in rules
        ),
    )
