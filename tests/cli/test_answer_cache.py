"""The answer cache: a run asks only what no earlier run was answered."""

import asyncio
import json
import os
import sys
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest

from klint.app import AppSettings
from klint.cli import (
    FILE_AUDIT_COMMAND,
    AuditCommandApp,
    ExitCode,
    run_command_from_shell,
)
from tests.support.builders import (
    FILE_RULE,
    build_audit_command_app,
    list_lines_before_judge_usage,
    make_settings,
    write_json,
    write_text,
)
from tests.support.fakes import FakeJudge, PickyJudge
from tests.support.paths import TIDY_RULE_PACK
from tests.support.stub_system_one_server import StubSystemOneServer

Capture = pytest.CaptureFixture[str]

RULE_IDS = ("a_rule", "b_rule", "c_rule")


def _build_app(
    judge: FakeJudge, cache_folder: Path | None, settings: AppSettings | None = None
) -> AuditCommandApp:
    settings = replace(settings or make_settings(), answer_cache_folder=cache_folder)
    return build_audit_command_app(FILE_AUDIT_COMMAND, judge, settings)


def _run(app: AuditCommandApp, target: Path, *options: str) -> ExitCode:
    return asyncio.run(app.run([str(target), "--json", "--all-answers", *options]))


def _read_output(capsys: Capture) -> tuple[dict[str, Any], str]:
    captured = capsys.readouterr()
    output: dict[str, Any] = json.loads(captured.out)
    return output, captured.err


def _write_project(tmp_path: Path) -> Path:
    write_text(tmp_path / "project" / "a.py", "x = 1\n")
    write_text(tmp_path / "project" / "b.py", "y = 2\n")
    return tmp_path / "project"


def _write_pack(tmp_path: Path, *rule_ids: str) -> Path:
    return write_json(
        tmp_path / "rules.json",
        {
            rule_id: {**FILE_RULE, "question": f"Is {rule_id} kept?"}
            for rule_id in rule_ids
        },
    )


def test_second_run_asks_nothing_and_reports_the_same(
    tmp_path: Path, capsys: Capture
) -> None:
    cache = tmp_path / "answers"
    project = _write_project(tmp_path)
    first_judge = FakeJudge(rule_id_to_answer={"tidy_file": "fail"}, confidence=0.7)
    second_judge = FakeJudge(default="pass")

    exit_code = _run(_build_app(first_judge, cache), project)
    cold, cold_err = _read_output(capsys)
    warm_exit_code = _run(_build_app(second_judge, cache), project)
    warm, warm_err = _read_output(capsys)

    assert exit_code == warm_exit_code == ExitCode.PROBLEMS_FOUND
    assert len(first_judge.requests) == 2
    assert second_judge.requests == []
    assert warm["findings"] == cold["findings"]
    assert warm["unit_id_to_roll_up_status"] == cold["unit_id_to_roll_up_status"]
    # A cached reply counts no request and no input tokens.
    assert cold["judge_usage"] == {"requests": 2, "input_tokens": None}
    assert warm["judge_usage"] == {"requests": 0, "input_tokens": 0}
    assert cold["answer_cache"] == {"questions_from_cache": 0, "questions_asked": 2}
    assert warm["answer_cache"] == {"questions_from_cache": 2, "questions_asked": 0}
    assert cold_err.splitlines()[-2:] == [
        "[klint] Answer cache: 0 questions answered from the cache, 2 asked",
        "[klint] Judge usage: 2 requests, input tokens not reported",
    ]
    assert warm_err.splitlines()[-2:] == [
        "[klint] Answer cache: 2 questions answered from the cache, 0 asked",
        "[klint] Judge usage: 0 requests, 0 input tokens",
    ]


def test_changed_unit_is_asked_again_and_the_others_are_not(
    tmp_path: Path, capsys: Capture
) -> None:
    cache = tmp_path / "answers"
    project = _write_project(tmp_path)
    _run(_build_app(FakeJudge(), cache), project)
    capsys.readouterr()
    write_text(project / "b.py", "y = 3\n")
    judge = FakeJudge()

    _run(_build_app(judge, cache), project)

    assert [request.subject for request in judge.requests] == ["y = 3\n"]
    assert _read_output(capsys)[0]["answer_cache"] == {
        "questions_from_cache": 1,
        "questions_asked": 1,
    }


def test_changed_question_is_asked_again_while_the_others_come_from_the_cache(
    tmp_path: Path, capsys: Capture
) -> None:
    cache = tmp_path / "answers"
    target = write_text(tmp_path / "a.py", "x = 1\n")
    pack = _write_pack(tmp_path, *RULE_IDS)
    _run(
        _build_app(FakeJudge(), cache, make_settings(built_in_rule_packs=[pack])),
        target,
    )
    capsys.readouterr()
    reworded = write_json(
        tmp_path / "rules.json",
        {
            **{
                rule_id: {**FILE_RULE, "question": f"Is {rule_id} kept?"}
                for rule_id in RULE_IDS
            },
            "b_rule": {**FILE_RULE, "question": "Is b_rule kept, really?"},
        },
    )
    judge = FakeJudge(rule_id_to_answer={"b_rule": "fail"})

    _run(
        _build_app(judge, cache, make_settings(built_in_rule_packs=[reworded])),
        target,
    )

    assert judge.list_asked_rule_ids() == [["b_rule"]]
    report = _read_output(capsys)[0]
    assert [(f["rule_id"], f["answer"]) for f in report["findings"]] == [
        ("b_rule", "Fail"),
        ("a_rule", "Pass"),
        ("c_rule", "Pass"),
    ]
    assert report["answer_cache"] == {"questions_from_cache": 2, "questions_asked": 1}


def test_another_model_version_is_asked_again(tmp_path: Path) -> None:
    cache = tmp_path / "answers"
    target = write_text(tmp_path / "a.py", "x = 1\n")
    _run(_build_app(FakeJudge(model_version="model-1"), cache), target)
    judge = FakeJudge(model_version="model-2")

    _run(_build_app(judge, cache), target)

    assert len(judge.requests) == 1


def test_failed_request_and_unanswered_question_are_not_stored(
    tmp_path: Path,
) -> None:
    cache = tmp_path / "answers"
    project = _write_project(tmp_path)
    pack = _write_pack(tmp_path, "a_rule", "b_rule")
    settings = make_settings(built_in_rule_packs=[pack])
    # The judge is down for a.py, and gives no answer to b_rule about b.py.
    first_judge = PickyJudge(refuses="x = 1")
    first_judge.rule_id_to_answer = {"b_rule": None}
    _run(_build_app(first_judge, cache, settings), project)
    judge = FakeJudge()

    _run(_build_app(judge, cache, settings), project)

    assert {
        request.subject: sorted(q.question_id for q in request.questions)
        for request in judge.requests
    } == {"x = 1\n": ["a_rule", "b_rule"], "y = 2\n": ["b_rule"]}


def test_same_request_twice_in_one_run_is_answered_once(tmp_path: Path) -> None:
    cache = tmp_path / "answers"
    write_text(tmp_path / "project" / "a.py", "x = 1\n")
    write_text(tmp_path / "project" / "pkg" / "a.py", "x = 1\n")
    judge = FakeJudge()

    _run(_build_app(judge, cache), tmp_path / "project")

    assert len(judge.requests) == 1


def test_corrupt_entry_is_a_miss_with_a_warning(
    tmp_path: Path, capsys: Capture
) -> None:
    cache = tmp_path / "answers"
    target = write_text(tmp_path / "a.py", "x = 1\n")
    _run(_build_app(FakeJudge(), cache), target)
    capsys.readouterr()
    (entry,) = cache.rglob("*.json")
    entry.write_text("{not json", encoding="utf-8")
    judge = FakeJudge()

    exit_code = _run(_build_app(judge, cache), target)

    assert exit_code == ExitCode.NO_PROBLEMS
    assert len(judge.requests) == 1
    _, stderr = _read_output(capsys)
    assert any(
        line.startswith(
            f"[klint] Warning: The answer cache entry '{entry}' is left out"
        )
        for line in stderr.splitlines()
    )
    assert json.loads(entry.read_text(encoding="utf-8"))["question_key_to_answer"]


def test_unresolved_model_version_leaves_the_cache_unused_with_a_warning(
    tmp_path: Path, capsys: Capture
) -> None:
    cache = tmp_path / "answers"
    target = write_text(tmp_path / "a.py", "x = 1\n")
    judge = FakeJudge(model_version=None)

    _run(_build_app(judge, cache), target)
    first_report, first_stderr = _read_output(capsys)
    _run(_build_app(judge, cache), target)

    report, stderr = _read_output(capsys)
    assert len(judge.requests) == 2
    assert "answer_cache" not in first_report
    assert "[klint] Warning: The answer cache is not used in this run" in first_stderr
    assert not cache.exists()
    assert "answer_cache" not in report
    assert "Answer cache:" not in stderr


def test_entry_records_the_klint_version_the_model_and_no_code(tmp_path: Path) -> None:
    cache = tmp_path / "answers"
    target = write_text(tmp_path / "a.py", "secret_code = 1\n")

    _run(_build_app(FakeJudge(model_version="model-1"), cache), target)

    (entry,) = cache.rglob("*.json")
    text = entry.read_text(encoding="utf-8")
    stored = json.loads(text)
    assert stored["model_version"] == "model-1"
    assert stored["klint_version"]
    assert stored["written_at"].startswith("20")
    assert "secret_code" not in text
    assert "Is the file tidy" not in text


def test_cache_off_from_the_shell_prints_no_cache_line(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    shell_env: dict[str, str],
    capsys: Capture,
    system_one_server: StubSystemOneServer,
) -> None:
    target = write_text(tmp_path / "a.py", "x = 1\n")
    shell_env["KLINT_JUDGE_MODE"] = "remote"
    shell_env["KLINT_JUDGE_BASE_URL"] = system_one_server.base_url
    shell_env["KLINT_ANSWER_CACHE"] = "OFF"
    monkeypatch.setattr(sys, "argv", ["klint", str(target), "--json"])

    asyncio.run(run_command_from_shell(FILE_AUDIT_COMMAND))
    asyncio.run(run_command_from_shell(FILE_AUDIT_COMMAND))

    assert len(system_one_server.list_posted_requests()) == 2
    stderr = capsys.readouterr().err
    assert "answer cache" not in stderr
    assert "Answer cache:" not in stderr


def test_cache_folder_from_the_shell_is_named_on_the_judge_line_and_used(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    shell_env: dict[str, str],
    capsys: Capture,
    system_one_server: StubSystemOneServer,
) -> None:
    system_one_server.response_body = {"answers": {"tidy_file": {"choice": "pass"}}}
    target = write_text(tmp_path / "a.py", "x = 1\n")
    shell_env["KLINT_JUDGE_MODE"] = "remote"
    shell_env["KLINT_JUDGE_BASE_URL"] = system_one_server.base_url
    shell_env["KLINT_JUDGE_MODEL"] = "jev-latest"
    shell_env["KLINT_REPLACE_FILE_RULES"] = str(TIDY_RULE_PACK)
    shell_env["KLINT_ANSWER_CACHE"] = str(tmp_path / "answers")
    monkeypatch.setattr(sys, "argv", ["klint", str(target), "--json"])

    asyncio.run(run_command_from_shell(FILE_AUDIT_COMMAND))
    first_err = capsys.readouterr().err
    asyncio.run(run_command_from_shell(FILE_AUDIT_COMMAND))
    second_err = capsys.readouterr().err

    assert list_lines_before_judge_usage(first_err)[0] == (
        f"[klint] Judge: jev-latest at {system_one_server.base_url} "
        f"(remote, no API key); answer cache at {tmp_path / 'answers'}"
    )
    assert first_err.splitlines()[-2] == (
        "[klint] Answer cache: 0 questions answered from the cache, 1 asked"
    )
    assert second_err.splitlines()[-2] == (
        "[klint] Answer cache: 1 question answered from the cache, 0 asked"
    )
    # One list of models per run, then one request for the one audit the cache
    # had no answer to.
    assert [r.path for r in system_one_server.received] == [
        "/v1/models",
        "/v1/systemone",
        "/v1/models",
    ]
    assert os.listdir(tmp_path / "answers")
