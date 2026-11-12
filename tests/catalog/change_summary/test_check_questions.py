"""The question each check asks, by the level of the summary it is asked about."""

import json

from klint.catalog.change_summary.change_summary_suite import SUMMARY_CHECKS_PACK
from klint.catalog.domain_neutral import locate_built_in_catalog_file
from tests.support.change_summary import (
    GREETING_HUNK,
    HypothesisJudge,
    run_change_summary_audit,
)

_COMPLETENESS_CHECKS = ("covers_every_change", "covers_key_changes")
_COMMIT_SUMMARY = "Greets people by their stripped name, and adds a README."
_FILE_SUMMARY = (
    "Greets a stripped name with 'Hello, <name>!' and drops an unused import."
)


def _read_rule_id_to_spec() -> dict[str, dict[str, object]]:
    path = locate_built_in_catalog_file(SUMMARY_CHECKS_PACK)
    rules: dict[str, dict[str, object]] = json.loads(path.read_text("utf-8"))["rules"]
    return rules


def _find_asked_questions(judge: HypothesisJudge, hypothesis: str) -> dict[str, str]:
    (request,) = [
        request
        for request in judge.requests
        if request.subject.endswith(f"Hypothesis: {hypothesis}")
    ]
    return {question.question_id: question.question for question in request.questions}


def test_a_hunk_summary_is_asked_each_check_s_own_question() -> None:
    judge = HypothesisJudge()

    run_change_summary_audit(judge)

    asked = _find_asked_questions(judge, str(GREETING_HUNK["summary"]))
    for rule_id, spec in _read_rule_id_to_spec().items():
        if rule_id in asked:
            assert asked[rule_id] == spec["question"], rule_id


def test_file_and_commit_summaries_are_asked_the_completeness_questions_for_them() -> (
    None
):
    judge = HypothesisJudge()

    outcome = run_change_summary_audit(judge)

    rule_id_to_spec = _read_rule_id_to_spec()
    for hypothesis, unit_type in (
        (_FILE_SUMMARY, "file_summary"),
        (_COMMIT_SUMMARY, "package_summary"),
    ):
        asked = _find_asked_questions(judge, hypothesis)
        for rule_id in _COMPLETENESS_CHECKS:
            unit_type_to_question = rule_id_to_spec[rule_id]["unit_type_to_question"]
            assert isinstance(unit_type_to_question, dict)
            assert asked[rule_id] == unit_type_to_question[unit_type]
            assert asked[rule_id] != rule_id_to_spec[rule_id]["question"]
    findings_on_commit = [
        finding
        for finding in outcome.report.list_findings()
        if finding.unit_id == "./" and finding.rule_id == "covers_every_change"
    ]
    assert [finding.question for finding in findings_on_commit] == [
        _find_asked_questions(judge, _COMMIT_SUMMARY)["covers_every_change"]
    ]
