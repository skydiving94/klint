"""The klint command cuts long files, classes and functions, and says so."""

import asyncio
import json
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest

from klint.cli import FILE_AUDIT_COMMAND
from klint.core.models.audits import DEFAULT_CHARACTER_BUDGET
from tests.support.builders import (
    FILE_RULE,
    build_audit_command_app,
    make_settings,
    write_json,
    write_text,
)
from tests.support.fakes import FakeJudge

Capture = pytest.CaptureFixture[str]

SHORT_FUNCTION = "def short() -> int:\n    return 1\n"


def _write_long_function(folder: Path) -> Path:
    body = "".join(f"    step_{index} = {index}\n" for index in range(200))
    return write_text(folder / "long.py", f"def long() -> None:\n{body}")


def _audit(
    tmp_path: Path, target: Path, capsys: Capture, *options: str
) -> tuple[FakeJudge, str]:
    """Audit ``target`` with a rule for each function; return the judge and stdout."""
    pack = write_json(
        tmp_path / "rules.json",
        {"short_function": {**FILE_RULE, "unit_types": ["function"]}},
    )
    judge = FakeJudge(default="fail")
    app = build_audit_command_app(
        FILE_AUDIT_COMMAND, judge, make_settings(built_in_rule_packs=[pack])
    )
    asyncio.run(app.run([str(target), *options]))
    return judge, capsys.readouterr().out


def test_finding_on_a_cut_function_names_the_budget(
    tmp_path: Path, capsys: Capture
) -> None:
    source = tmp_path / "source"
    long_file = _write_long_function(source)
    short_file = write_text(source / "short.py", SHORT_FUNCTION)

    _, output = _audit(tmp_path, source, capsys, "--json")

    findings: list[dict[str, Any]] = json.loads(output)["findings"]
    unit_id_to_cut = {
        finding["unit_id"]: finding["cut_at_characters"] for finding in findings
    }
    assert unit_id_to_cut == {
        f"{long_file}::long": DEFAULT_CHARACTER_BUDGET,
        f"{short_file}::short": None,
    }


def test_report_says_a_function_was_cut(tmp_path: Path, capsys: Capture) -> None:
    long_file = _write_long_function(tmp_path / "source")

    _, output = _audit(tmp_path, long_file, capsys)

    assert (
        f"(cut: judged on the first {DEFAULT_CHARACTER_BUDGET} characters only)"
        in output
    )


def test_report_says_nothing_of_a_cut_on_a_short_function(
    tmp_path: Path, capsys: Capture
) -> None:
    short_file = write_text(tmp_path / "source" / "short.py", SHORT_FUNCTION)

    _, output = _audit(tmp_path, short_file, capsys)

    assert "short_function" in output
    assert "cut:" not in output


def _write_function_of(folder: Path, length: int) -> Path:
    """Write a module whose one function is at least ``length`` characters long."""
    lines = ["def long() -> None:"]
    while sum(len(line) + 1 for line in lines) < length:
        lines.append(f"    step_{len(lines)} = {len(lines)}")
    return write_text(folder / "long.py", "\n".join(lines) + "\n")


@pytest.mark.parametrize(
    ("model_name", "character_budget"),
    [
        ("jaredpalmer/kev-4b", 2_000),
        ("jaredpalmer/kev-9b", 8_000),
        ("jev-latest", 60_000),
        ("some-other-model", DEFAULT_CHARACTER_BUDGET),
    ],
)
def test_function_is_cut_at_the_budget_of_the_judge_in_use(
    tmp_path: Path, capsys: Capture, model_name: str, character_budget: int
) -> None:
    long_file = _write_function_of(tmp_path / "source", 70_000)
    pack = write_json(
        tmp_path / "rules.json",
        {"short_function": {**FILE_RULE, "unit_types": ["function"]}},
    )
    judge = FakeJudge(default="fail")
    settings = replace(make_settings(built_in_rule_packs=[pack]), model_name=model_name)
    app = build_audit_command_app(FILE_AUDIT_COMMAND, judge, settings)

    asyncio.run(app.run([str(long_file), "--json"]))

    [request] = judge.requests
    assert character_budget - 100 < len(request.subject) <= character_budget
    [finding] = json.loads(capsys.readouterr().out)["findings"]
    assert finding["cut_at_characters"] == character_budget


def test_function_within_the_judge_budget_is_shown_whole(
    tmp_path: Path, capsys: Capture
) -> None:
    long_file = _write_function_of(tmp_path / "source", 5_000)
    pack = write_json(
        tmp_path / "rules.json",
        {"short_function": {**FILE_RULE, "unit_types": ["function"]}},
    )
    judge = FakeJudge(default="fail")
    settings = replace(
        make_settings(built_in_rule_packs=[pack]), model_name="jev-latest"
    )
    app = build_audit_command_app(FILE_AUDIT_COMMAND, judge, settings)

    asyncio.run(app.run([str(long_file), "--json"]))

    [request] = judge.requests
    assert request.subject == long_file.read_text(encoding="utf-8").rstrip("\n")
    [finding] = json.loads(capsys.readouterr().out)["findings"]
    assert finding["cut_at_characters"] is None
