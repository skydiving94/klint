"""The audit service: which rules reach the judge and what comes back."""

import asyncio
from pathlib import Path

from src.core.services.audit_service import AuditService
from src.infrastructure.extractors.file_extractor import WholeFileExtractor
from src.infrastructure.rules.json_loader import JsonRuleLoader
from tests.helpers import DIR_RULE, FILE_RULE, FakeJudge, write_json


def _service(rules_path: Path, judge: FakeJudge) -> AuditService:
    return AuditService(
        extractor=WholeFileExtractor(),
        evaluator=judge.evaluator(),
        rule_loader=JsonRuleLoader(rules_path),
    )


def test_service_asks_only_rules_that_apply_to_the_unit(
    tmp_path: Path, fake_judge: type[FakeJudge]
) -> None:
    rules = write_json(
        tmp_path / "rules.json", {"for_file": FILE_RULE, "for_dir": DIR_RULE}
    )
    target = tmp_path / "a.py"
    target.write_text("x = 1\ny = 2\n", encoding="utf-8")
    judge = fake_judge(default="fail")

    report = asyncio.run(_service(rules, judge).run_audit(target))

    assert judge.asked_rule_ids() == [["for_file"]]
    assert judge.calls[0][0] == "x = 1\ny = 2\n"
    (issue,) = report.get_issues()
    assert issue["rule_id"] == "for_file"
    assert issue["judgment"] == "Fail"
    assert issue["unit_id"] == issue["file_path"] == str(target)
    assert issue["line_range"] == [1, 2]


def test_service_does_not_call_the_judge_when_no_rule_applies(
    tmp_path: Path, fake_judge: type[FakeJudge]
) -> None:
    rules = write_json(tmp_path / "rules.json", {"for_dir": DIR_RULE})
    target = tmp_path / "a.py"
    target.write_text("x = 1\n", encoding="utf-8")
    judge = fake_judge()

    report = asyncio.run(_service(rules, judge).run_audit(target))

    assert judge.calls == []
    assert report.get_issues(fails_only=False) == []
