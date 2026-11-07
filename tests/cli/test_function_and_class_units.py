"""The klint command on the classes and functions of Python files."""

import asyncio
import json
import re
from pathlib import Path
from typing import Any

import pytest

from klint.app import AppSettings
from klint.cli import FILE_AUDIT_COMMAND, ExitCode
from klint.core.interfaces import BaseJudge
from tests.support.builders import (
    FILE_RULE,
    build_audit_command_app,
    make_settings,
    write_json,
    write_text,
)
from tests.support.fakes import FakeJudge, SubjectJudge

Capture = pytest.CaptureFixture[str]
_ANSI_CODE = re.compile(r"\x1b\[[0-9;]*m")

CLASS_RULE = {**FILE_RULE, "unit_types": ["class"]}
FUNCTION_RULE = {**FILE_RULE, "unit_types": ["function"]}

CART_SOURCE = '''import json


class Cart:
    """A shopping cart."""

    def add(self, item: str) -> None:
        self.items.append(item)

    def total(self) -> int:
        """Return the sum of the prices."""
        return sum(len(item) for item in self.items)


def load(text: str) -> Cart:
    return json.loads(text)
'''
CART_CLASS_SUBJECT = '''class Cart:
    """A shopping cart."""

    def add(self, item: str) -> None:
        ...

    def total(self) -> int:
        """Return the sum of the prices."""
        ...'''
ADD_METHOD_SUBJECT = """def add(self, item: str) -> None:
    self.items.append(item)"""
LOAD_FUNCTION_SUBJECT = """def load(text: str) -> Cart:
    return json.loads(text)"""


def _build_settings(tmp_path: Path, **rules: dict[str, Any]) -> AppSettings:
    """Return settings whose one built-in pack holds ``rules``."""
    pack = write_json(tmp_path / "rules.json", rules)
    return make_settings(built_in_rule_packs=[pack])


def _run(
    judge: BaseJudge, settings: AppSettings, target: Path, *options: str
) -> ExitCode:
    app = build_audit_command_app(FILE_AUDIT_COMMAND, judge, settings)
    return asyncio.run(app.run([str(target), *options]))


def _read_json(capsys: Capture) -> dict[str, Any]:
    output: dict[str, Any] = json.loads(capsys.readouterr().out)
    return output


def test_function_rule_flags_the_function_with_its_path_and_line_range(
    tmp_path: Path, capsys: Capture
) -> None:
    cart = write_text(tmp_path / "cart.py", CART_SOURCE)
    settings = _build_settings(tmp_path, short_function=FUNCTION_RULE)
    judge = SubjectJudge({ADD_METHOD_SUBJECT: "fail"})

    exit_code = _run(judge, settings, cart, "--json")

    assert exit_code == ExitCode.PROBLEMS_FOUND
    [finding] = _read_json(capsys)["findings"]
    assert finding["unit_id"] == f"{cart}::Cart.add"
    assert finding["location"] == {"path": str(cart), "start_line": 7, "end_line": 8}
    assert finding["context"] == {"qualified_name": "Cart.add"}
    # Each method and function is asked on its own, about its own source.
    assert judge.map_subject_to_asked_rule_ids() == {
        ADD_METHOD_SUBJECT: {"short_function"},
        """def total(self) -> int:
    \"\"\"Return the sum of the prices.\"\"\"
    return sum(len(item) for item in self.items)""": {"short_function"},
        LOAD_FUNCTION_SUBJECT: {"short_function"},
    }


def test_class_rule_reads_the_class_with_each_method_body_left_out(
    tmp_path: Path, capsys: Capture
) -> None:
    cart = write_text(tmp_path / "cart.py", CART_SOURCE)
    settings = _build_settings(tmp_path, focused_class=CLASS_RULE)
    judge = SubjectJudge({CART_CLASS_SUBJECT: "fail"})

    _run(judge, settings, cart, "--json")

    [finding] = _read_json(capsys)["findings"]
    assert finding["unit_id"] == f"{cart}::Cart"
    assert finding["location"] == {"path": str(cart), "start_line": 4, "end_line": 12}
    assert judge.map_subject_to_asked_rule_ids() == {
        CART_CLASS_SUBJECT: {"focused_class"}
    }


def test_file_rule_still_reads_the_whole_file_and_nothing_else(
    tmp_path: Path, capsys: Capture
) -> None:
    cart = write_text(tmp_path / "cart.py", CART_SOURCE)
    settings = _build_settings(
        tmp_path, tidy_file=FILE_RULE, short_function=FUNCTION_RULE
    )
    judge = SubjectJudge({CART_SOURCE: "fail"})

    _run(judge, settings, cart, "--json")

    [finding] = _read_json(capsys)["findings"]
    assert finding["rule_id"] == "tidy_file"
    assert finding["unit_id"] == str(cart)
    assert finding["location"] == {"path": str(cart), "start_line": 1, "end_line": 16}
    assert finding["context"] == {}
    subject_to_asked_rule_ids = judge.map_subject_to_asked_rule_ids()
    assert subject_to_asked_rule_ids[CART_SOURCE] == {"tidy_file"}
    assert subject_to_asked_rule_ids[LOAD_FUNCTION_SUBJECT] == {"short_function"}


def test_method_problem_rolls_up_to_its_class_and_its_file(
    tmp_path: Path, capsys: Capture
) -> None:
    cart = write_text(tmp_path / "cart.py", CART_SOURCE)
    settings = _build_settings(
        tmp_path,
        tidy_file=FILE_RULE,
        focused_class=CLASS_RULE,
        short_function=FUNCTION_RULE,
    )
    judge = SubjectJudge({ADD_METHOD_SUBJECT: "fail"})

    _run(judge, settings, cart, "--json")
    output = _read_json(capsys)
    _run(judge, settings, cart)
    report = _ANSI_CODE.sub("", capsys.readouterr().out)

    # Each unit comes before the units nested in it.
    assert output["unit_id_to_roll_up_status"] == {
        str(cart): "descendant_problem",
        f"{cart}::Cart": "descendant_problem",
        f"{cart}::Cart.add": "own_problem",
        f"{cart}::Cart.total": "no_problem",
        f"{cart}::load": "no_problem",
    }
    targets = [line for line in report.splitlines() if line.startswith("Target:")]
    assert targets == [
        f"Target: {cart} [DESCENDANT PROBLEM]",
        f"Target: {cart}::Cart [DESCENDANT PROBLEM]",
        f"Target: {cart}::Cart.add [OWN PROBLEM]",
    ]
    assert "short_function (lines 7-8)" in report


def test_unparseable_python_file_is_still_judged_whole_with_a_warning(
    tmp_path: Path, capsys: Capture
) -> None:
    broken = write_text(tmp_path / "broken.py", "def load(:\n    pass\n")
    settings = _build_settings(
        tmp_path, tidy_file=FILE_RULE, short_function=FUNCTION_RULE
    )
    judge = FakeJudge(default="fail")

    exit_code = _run(judge, settings, broken, "--json")

    captured = capsys.readouterr()
    assert exit_code == ExitCode.PROBLEMS_FOUND
    assert [finding["unit_id"] for finding in json.loads(captured.out)["findings"]] == [
        str(broken)
    ]
    assert captured.err.startswith(
        f"[klint] Warning: File '{broken}' is judged as a whole only: it cannot be "
        "parsed (invalid syntax, line 1), so its classes and functions are not "
        "judged on their own\n"
    )
    assert judge.list_asked_rule_ids() == [["tidy_file"]]


def test_file_of_another_language_has_no_function_units(
    tmp_path: Path, fake_judge: type[FakeJudge]
) -> None:
    script = write_text(tmp_path / "cart.ts", "function load(): void {}\n")
    settings = _build_settings(
        tmp_path, tidy_file=FILE_RULE, short_function=FUNCTION_RULE
    )
    judge = fake_judge()

    _run(judge, settings, script, "--json")

    assert judge.list_asked_rule_ids() == [["tidy_file"]]
