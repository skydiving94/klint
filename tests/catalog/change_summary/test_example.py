"""The change-summary example: two documents that differ in two planted summaries.

Each comes in two forms: with the code of each hunk, and with summaries
only, whose change, commit d35fa76, klint reads from git.
"""

import asyncio
import json
import subprocess
from dataclasses import asdict
from pathlib import Path

import pytest

from klint.app.pipeline import AuditOutcome, AuditRequest
from klint.catalog.change_summary import CHANGE_SUMMARY_KIND_ID
from klint.core.models.audits import DiskPathInput
from tests.support.builders import build_audit_pipeline
from tests.support.change_summary import HypothesisJudge, extract_summary_units
from tests.support.paths import REPO_ROOT

_EXAMPLE = REPO_ROOT / "examples" / "change_summary"
# The phrase of each planted error: a false statement and an unsupported reason.
_PLANTED_PHRASE_TO_RULE_ID_TO_CHOICE = {
    "raises a ValueError": {"no_false_statement": "inaccurate"},
    "ran out of memory": {"no_unsupported_reason": "inaccurate"},
}
_PLANTED_UNIT_IDS = [
    "src/catalog/code/common/extractors/traits_based_extraction_delegator.py#3",
    "tests/",
]


def _map_unit_id_to_summary(path: Path) -> dict[str, str]:
    units = extract_summary_units(json.loads(path.read_text(encoding="utf-8")))
    return {unit.unit_id: asdict(unit.get_context())["summary"] for unit in units}


def _verify_example(document_name: str, judge: HypothesisJudge) -> AuditOutcome:
    request = AuditRequest(
        audit_input=DiskPathInput(path=_EXAMPLE / document_name),
        audit_kind_id=CHANGE_SUMMARY_KIND_ID,
    )
    return asyncio.run(build_audit_pipeline(judge).run_audit(request))


@pytest.fixture
def example_commit(in_repo_root: Path) -> None:
    """Run from the repository root; skip where commit d35fa76 is not cloned."""
    found = subprocess.run(
        ["git", "cat-file", "-e", "d35fa76^{commit}"],
        cwd=in_repo_root,
        capture_output=True,
        check=False,
    )
    if found.returncode != 0:
        pytest.skip("commit d35fa76 is not in this clone, as in a shallow one")


def test_the_planted_document_differs_only_in_its_two_planted_summaries() -> None:
    clean = _map_unit_id_to_summary(_EXAMPLE / "summaries.json")
    planted = _map_unit_id_to_summary(_EXAMPLE / "summaries_with_planted_errors.json")

    assert clean.keys() == planted.keys()
    assert len(clean) == 17
    assert (
        sorted(unit_id for unit_id in clean if clean[unit_id] != planted[unit_id])
        == _PLANTED_UNIT_IDS
    )


@pytest.mark.usefixtures("example_commit")
def test_the_summaries_only_example_shows_the_judge_what_the_full_one_does() -> None:
    full_judge = HypothesisJudge()
    summaries_only_judge = HypothesisJudge()

    full = _verify_example("summaries.json", full_judge)
    summaries_only = _verify_example("summaries_only.json", summaries_only_judge)

    assert summaries_only.selected_unit_ids == full.selected_unit_ids
    assert len(full.selected_unit_ids) == 17
    assert sorted(summaries_only_judge.list_hypotheses()) == sorted(
        full_judge.list_hypotheses()
    )
    assert sorted(request.subject for request in summaries_only_judge.requests) == (
        sorted(request.subject for request in full_judge.requests)
    )


@pytest.mark.usefixtures("example_commit")
def test_the_planted_summaries_only_example_flags_the_same_summaries() -> None:
    outcomes = [
        _verify_example(
            document_name, HypothesisJudge(_PLANTED_PHRASE_TO_RULE_ID_TO_CHOICE)
        )
        for document_name in (
            "summaries_with_planted_errors.json",
            "summaries_only_with_planted_errors.json",
        )
    ]

    full_flags, summaries_only_flags = (
        sorted(
            (finding.unit_id, finding.rule_id)
            for finding in outcome.report.select_findings()
        )
        for outcome in outcomes
    )
    assert summaries_only_flags == full_flags
    assert [unit_id for unit_id, _ in full_flags] == _PLANTED_UNIT_IDS
