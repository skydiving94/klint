"""The change-summary audit: each level checked after the levels below it."""

import asyncio
import json
from dataclasses import asdict

from klint.app.pipeline.audit_pipeline import AuditRequest
from klint.catalog.change_summary import CHANGE_SUMMARY_KIND_ID
from klint.core.models.audit_input import InMemoryBytesInput
from klint.core.models.location import Location
from klint.core.models.roll_up_status import RollUpStatus
from tests.support.builders import build_audit_pipeline, build_rule_pack
from tests.support.change_summary import (
    GREET_FILE_POINTER,
    GREETING_DOCUMENT,
    HypothesisJudge,
    extract_summary_units,
    run_change_summary_audit,
)
from tests.support.fakes import InMemoryRuleSource

_ACCURACY_CHECKS = [
    "no_false_statement",
    "no_unsupported_reason",
]
_COMPLETENESS_CHECKS = ["covers_every_change", "covers_key_changes"]


def test_every_summary_is_judged_after_the_summaries_nested_in_it() -> None:
    judge = HypothesisJudge()

    run_change_summary_audit(judge)

    hypotheses = judge.list_hypotheses()
    units = extract_summary_units(GREETING_DOCUMENT)
    unit_id_to_summary = {
        unit.unit_id: asdict(unit.get_context())["summary"] for unit in units
    }
    assert sorted(hypotheses) == sorted(unit_id_to_summary.values())
    for unit in units:
        for child in unit.children():
            assert hypotheses.index(unit_id_to_summary[child.unit_id]) < (
                hypotheses.index(unit_id_to_summary[unit.unit_id])
            )


def test_each_level_is_asked_its_checks() -> None:
    judge = HypothesisJudge()

    run_change_summary_audit(judge)

    hunk_checks = sorted([*_ACCURACY_CHECKS, *_COMPLETENESS_CHECKS])
    upper_level_checks = sorted([*hunk_checks, "no_contradiction_with_level_below"])
    assert sorted(map(tuple, judge.asked_rule_ids())) == sorted(
        [tuple(hunk_checks)] * 3 + [tuple(upper_level_checks)] * 4
    )


def test_a_false_hunk_summary_is_inaccurate_and_its_ancestors_show_it() -> None:
    judge = HypothesisJudge(
        {"Removes the unused import": {"no_false_statement": "inaccurate"}}
    )

    report = run_change_summary_audit(judge).report

    (finding,) = report.select_findings()
    assert (finding.unit_id, finding.rule_id, finding.answer.key) == (
        "app/greet.py#2",
        "no_false_statement",
        "inaccurate",
    )
    assert report.map_unit_id_to_roll_up_status() == {
        "./": RollUpStatus.DESCENDANT_PROBLEM,
        "app/": RollUpStatus.DESCENDANT_PROBLEM,
        "app/greet.py": RollUpStatus.DESCENDANT_PROBLEM,
        "app/greet.py#1": RollUpStatus.NO_PROBLEM,
        "app/greet.py#2": RollUpStatus.OWN_PROBLEM,
        "README.md": RollUpStatus.NO_PROBLEM,
        "README.md#1": RollUpStatus.NO_PROBLEM,
    }


def test_accuracy_findings_are_listed_before_completeness_findings() -> None:
    judge = HypothesisJudge(
        {
            "Greets a stripped name with 'Hello, <name>!' and drops": {
                "covers_key_changes": "inaccurate",
                "covers_every_change": "inaccurate",
                "no_unsupported_reason": "inaccurate",
                "no_contradiction_with_level_below": "inaccurate",
            }
        }
    )

    findings = run_change_summary_audit(judge).report.select_findings()

    assert [(finding.rule_id, finding.tags) for finding in findings] == [
        ("no_contradiction_with_level_below", ("accuracy",)),
        ("no_unsupported_reason", ("accuracy",)),
        ("covers_every_change", ("completeness",)),
        ("covers_key_changes", ("completeness",)),
    ]


def test_a_finding_points_at_the_summary_and_at_the_code_it_is_about() -> None:
    judge = HypothesisJudge({"Strips the name": {"no_false_statement": "inaccurate"}})

    (finding,) = run_change_summary_audit(judge).report.select_findings()

    assert finding.location == Location(f"{GREET_FILE_POINTER}/hunks/0/summary")
    assert finding.evidence_location == Location("app/greet.py", 3, 4)
    assert asdict(finding.context) == {
        "level": "hunk",
        "path": "app/greet.py",
        "summary": "Strips the name and greets it with 'Hello, <name>!' "
        "instead of 'hi'.",
    }


def test_a_problem_below_the_least_confidence_rolls_up_to_no_one() -> None:
    judge = HypothesisJudge({"Strips the name": {"no_false_statement": "inaccurate"}})
    judge.confidence = 0.5

    report = run_change_summary_audit(judge, min_confidence=0.8).report

    assert set(report.map_unit_id_to_roll_up_status().values()) == {
        RollUpStatus.NO_PROBLEM
    }


def test_custom_rules_are_asked_beside_the_summary_checks() -> None:
    judge = HypothesisJudge()
    custom_rules = InMemoryRuleSource(
        build_rule_pack("custom", "names_a_ticket", target_unit_types=("file_summary",))
    )
    request = AuditRequest(
        audit_input=InMemoryBytesInput(
            content=json.dumps(GREETING_DOCUMENT).encode(),
            media_type="application/json",
        ),
        audit_kind_id=CHANGE_SUMMARY_KIND_ID,
        custom_rule_source=custom_rules,
    )

    asyncio.run(build_audit_pipeline(judge).run_audit(request))

    asked_rule_ids = judge.subject_to_asked_rule_ids()
    assert (
        sum("names_a_ticket" in rule_ids for rule_ids in asked_rule_ids.values()) == 2
    )
