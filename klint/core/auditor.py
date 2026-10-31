import asyncio
from collections import defaultdict
from collections.abc import Sequence

from injector import inject

from klint.core.interfaces.audit_progress_listener import BaseAuditProgressListener
from klint.core.interfaces.judge import BaseJudge
from klint.core.models.audit_order import AuditOrder
from klint.core.models.judge_exchange import JudgeQuestion, JudgeRequest
from klint.core.models.report import AuditFinding, AuditReport
from klint.core.models.rule import AuditRule
from klint.core.models.rule_set import RuleSet
from klint.core.models.scale import AnswerScale
from klint.core.models.unit import AuditableUnit
from klint.core.models.unit_tree import (
    list_ancestor_unit_ids,
    map_unit_id_to_parent_unit_id,
)

# The most units audited at the same time.
_MAX_CONCURRENT_AUDITS = 8


class Auditor:
    """Audits units and reports what the judge finds.

    Asks the judge the rules a rule set chooses for each unit, a limited
    number of units at a time, in the order the audit asks for, and turns
    the answers into findings. A unit whose audit fails is left out and the
    others go on.
    """

    @inject
    def __init__(self, judge: BaseJudge) -> None:
        self._judge = judge

    async def audit(
        self,
        units: Sequence[AuditableUnit],
        rule_set: RuleSet,
        answer_scale: AnswerScale,
        audit_progress_listener: BaseAuditProgressListener | None = None,
        audit_order: AuditOrder = AuditOrder.ALL_AT_ONCE,
    ) -> AuditReport:
        """Audit each unit with the rules ``rule_set`` chooses; return the report.

        The judge answers each rule on ``answer_scale``. With CHILDREN_FIRST,
        the units are judged a level at a time, the deepest first, so that
        each is judged after the units nested inside it; the limit on units
        judged at once applies within a level. Whatever the order, the report
        holds the units audited without error, and their findings, in the
        order of ``units``. The listener, when given, is told when the audit
        starts and about each unit as its audit ends.
        """
        if audit_progress_listener is not None:
            audit_progress_listener.report_audit_started(len(units))
        semaphore = asyncio.Semaphore(_MAX_CONCURRENT_AUDITS)

        async def audit_one(unit: AuditableUnit) -> list[AuditFinding] | None:
            """Return the findings on ``unit``; None when its audit fails."""
            async with semaphore:
                try:
                    findings = await self._audit_unit(
                        unit, rule_set.select_rules_for(unit), answer_scale
                    )
                except Exception as error:
                    # Whatever went wrong, such as the judge not answering,
                    # only this unit is left out.
                    if audit_progress_listener is not None:
                        audit_progress_listener.report_unit_failed(unit.unit_id, error)
                    return None
            if audit_progress_listener is not None:
                audit_progress_listener.report_unit_audited(unit.unit_id)
            return findings

        unit_findings: list[list[AuditFinding] | None] = [None] * len(units)
        for level in _order_levels(units, audit_order):
            level_findings = await asyncio.gather(
                *(audit_one(units[index]) for index in level)
            )
            for index, findings in zip(level, level_findings, strict=True):
                unit_findings[index] = findings
        report = AuditReport()
        for unit, findings in zip(units, unit_findings, strict=True):
            if findings is None:
                continue
            report.record_audited_unit(unit.unit_id)
            for finding in findings:
                report.record(finding)
        return report

    async def _audit_unit(
        self,
        unit: AuditableUnit,
        rules: Sequence[AuditRule],
        answer_scale: AnswerScale,
    ) -> list[AuditFinding]:
        """Ask the judge ``rules`` about one unit; none means no call."""
        if not rules:
            return []
        answers = await self._judge.answer(_build_request(unit, rules, answer_scale))
        question_id_to_answer = {answer.question_id: answer for answer in answers}
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
                    question=rule.instructions,
                    confidence=answer.confidence,
                    choice_key_to_probability=answer.choice_key_to_probability,
                    tags=tuple(rule.tags),
                    location=unit.get_location(),
                    evidence_location=unit.get_evidence_location(),
                    context=unit.get_context(),
                )
            )
        return findings


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
    unit: AuditableUnit, rules: Sequence[AuditRule], answer_scale: AnswerScale
) -> JudgeRequest:
    """Return the request that asks each rule about ``unit``, by rule id."""
    choice_key_to_criterion = answer_scale.map_choice_key_to_criterion()
    return JudgeRequest(
        subject=unit.get_content(),
        questions=tuple(
            JudgeQuestion(
                question_id=rule.rule_id,
                question_type=rule.question_type,
                question=rule.instructions,
                choice_key_to_criterion=choice_key_to_criterion,
            )
            for rule in rules
        ),
    )
