"""The klint-change-summary command, run on a change-summary document on disk."""

import asyncio
import json
import re
from pathlib import Path

import pytest

from klint.cli.change_summary_audit import CHANGE_SUMMARY_COMMAND
from klint.cli.exit_code import ExitCode
from tests.support.builders import build_audit_command_app, write_text
from tests.support.change_summary import (
    GREETING_DOCUMENT,
    HypothesisJudge,
    copy_greeting_document,
)

Capture = pytest.CaptureFixture[str]
_ANSI_CODE = re.compile(r"\x1b\[[0-9;]*m")
_FALSE_IMPORT_HUNK = {"Removes the unused import": {"no_false_statement": "inaccurate"}}


def _run_command(
    tmp_path: Path,
    judge: HypothesisJudge,
    *options: str,
    document: object = GREETING_DOCUMENT,
) -> ExitCode:
    summaries = write_text(tmp_path / "summaries.json", json.dumps(document))
    app = build_audit_command_app(CHANGE_SUMMARY_COMMAND, judge)
    return asyncio.run(app.run([str(summaries), *options]))


def test_a_document_whose_summaries_all_pass_exits_0(
    tmp_path: Path, capsys: Capture
) -> None:
    exit_code = _run_command(tmp_path, HypothesisJudge())

    report = _ANSI_CODE.sub("", capsys.readouterr().out)
    assert exit_code == ExitCode.NO_PROBLEMS
    assert "(1 files scanned, 7 units audited)" in report
    assert "✔ Every summary passed its checks." in report


def test_a_false_summary_is_reported_on_its_level_and_its_ancestors(
    tmp_path: Path, capsys: Capture
) -> None:
    exit_code = _run_command(tmp_path, HypothesisJudge(_FALSE_IMPORT_HUNK))

    report = _ANSI_CODE.sub("", capsys.readouterr().out)
    assert exit_code == ExitCode.PROBLEMS_FOUND
    assert [line for line in report.splitlines() if line.startswith("Target:")] == [
        "Target: ./ [DESCENDANT PROBLEM]",
        "Target: app/ [DESCENDANT PROBLEM]",
        "Target: app/greet.py [DESCENDANT PROBLEM]",
        "Target: app/greet.py#2 [OWN PROBLEM]",
    ]
    assert (
        "  [INACCURATE] no_false_statement (evidence: app/greet.py lines 1-1)  "
        "Confidence:"
    ) in report


def test_json_lists_each_summary_its_status_and_the_findings(
    tmp_path: Path, capsys: Capture
) -> None:
    exit_code = _run_command(tmp_path, HypothesisJudge(_FALSE_IMPORT_HUNK), "--json")

    output = json.loads(capsys.readouterr().out)
    assert exit_code == ExitCode.PROBLEMS_FOUND
    assert output["examined_summaries"] == [
        "./",
        "app/",
        "app/greet.py",
        "app/greet.py#1",
        "app/greet.py#2",
        "README.md",
        "README.md#1",
    ]
    assert output["unit_id_to_roll_up_status"]["app/greet.py#2"] == "own_problem"
    assert output["unit_id_to_roll_up_status"]["./"] == "descendant_problem"
    (finding,) = output["findings"]
    assert finding["answer"] == "Inaccurate"
    assert finding["tags"] == ["accuracy"]
    assert finding["context"] == {
        "level": "hunk",
        "path": "app/greet.py",
        "summary": "Removes the unused import of os.",
    }
    assert finding["location"]["source"].endswith("/hunks/1/summary")


def test_every_judgment_is_shown_with_all(tmp_path: Path, capsys: Capture) -> None:
    _run_command(tmp_path, HypothesisJudge(), "--all", "--json")

    findings = json.loads(capsys.readouterr().out)["findings"]
    assert {finding["answer"] for finding in findings} == {"Accurate"}
    assert len(findings) == 3 * 4 + 4 * 5


def test_a_document_of_the_wrong_shape_stops_the_command_with_exit_2(
    tmp_path: Path, capsys: Capture
) -> None:
    document = copy_greeting_document()
    document["schema_version"] = 7

    exit_code = _run_command(tmp_path, HypothesisJudge(), document=document)

    assert exit_code == ExitCode.RUN_ERROR
    assert capsys.readouterr().err.splitlines() == [
        "[klint-change-summary] Error: Change-summary document: #/schema_version "
        "is 7; klint reads schema_version 1 only"
    ]


def test_a_file_that_is_not_json_stops_the_command_with_exit_2(
    tmp_path: Path, capsys: Capture
) -> None:
    summaries = write_text(tmp_path / "summaries.json", "{ not json")
    app = build_audit_command_app(CHANGE_SUMMARY_COMMAND, HypothesisJudge())

    exit_code = asyncio.run(app.run([str(summaries)]))

    assert exit_code == ExitCode.RUN_ERROR
    assert "is not valid JSON" in capsys.readouterr().err


def test_an_unknown_field_is_one_warning_line_and_the_command_goes_on(
    tmp_path: Path, capsys: Capture
) -> None:
    document = copy_greeting_document()
    document["root_package"]["summery"] = "A typo."

    exit_code = _run_command(tmp_path, HypothesisJudge(), document=document)

    assert exit_code == ExitCode.NO_PROBLEMS
    assert capsys.readouterr().err.splitlines() == [
        "[klint-change-summary] Warning: Change-summary document: #/root_package "
        "has unknown fields ['summery'], which are ignored; known fields: "
        "['files', 'packages', 'path', 'summary']"
    ]
