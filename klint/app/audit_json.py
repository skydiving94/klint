"""An audit's outcome as JSON output writes it, the same for every front end."""

from collections.abc import Sequence

from klint.app.pipeline import AuditOutcome
from klint.app.staged_change import StagedChangeScope, convert_staged_change_to_dict
from klint.core.models.judging import JudgeUsage
from klint.core.models.reports import AuditFinding


def convert_judge_usage_to_dict(usage: JudgeUsage) -> dict[str, int | None]:
    """Return the judge's usage as JSON output writes it.

    input_tokens is null when the judge did not report them.
    """
    return {"requests": usage.request_count, "input_tokens": usage.input_token_count}


def convert_answer_cache_to_dict(usage: JudgeUsage) -> dict[str, int]:
    """Return the answer cache's counts as JSON output writes them."""
    return {
        "questions_from_cache": usage.cached_question_count,
        "questions_asked": usage.asked_question_count,
    }


def convert_audit_outcome_to_dict(
    outcome: AuditOutcome,
    findings: Sequence[AuditFinding],
    audited_units_json_key: str,
    staged: StagedChangeScope | None = None,
) -> dict[str, object]:
    """Return ``outcome`` as JSON output writes it, with ``findings`` as selected.

    The audited units are listed under ``audited_units_json_key``. The keys
    present in every output come first; "answer_cache" is present only when
    the answer cache took part, "applied_rule_exclusions" only when the
    project's klint.json turned a rule off, and "staged_change" only for an
    audit of the staged change, so that a plain run gets the same JSON as
    before each was added.
    """
    report = outcome.report
    usage = report.get_judge_usage()
    json_report: dict[str, object] = {
        audited_units_json_key: report.list_audited_unit_ids(),
        "unit_id_to_roll_up_status": {
            unit_id: status.value
            for unit_id, status in report.map_unit_id_to_roll_up_status().items()
        },
        "findings": [finding.convert_to_dict() for finding in findings],
        "judge_usage": convert_judge_usage_to_dict(usage),
    }
    if usage.did_cache_take_part():
        json_report["answer_cache"] = convert_answer_cache_to_dict(usage)
    if outcome.applied_rule_exclusions:
        json_report["applied_rule_exclusions"] = [
            applied.convert_to_dict() for applied in outcome.applied_rule_exclusions
        ]
    if staged is not None:
        json_report["staged_change"] = convert_staged_change_to_dict(
            staged, outcome.extracted_unit_count, outcome.selected_unit_count
        )
    return json_report
