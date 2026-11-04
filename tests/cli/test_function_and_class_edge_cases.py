"""The klint command on Python functions and classes of unusual shapes."""

import asyncio
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

from klint.app import AppSettings
from klint.cli import FILE_AUDIT_COMMAND
from klint.core.models.audits import DEFAULT_CHARACTER_BUDGET
from klint.core.models.units import Location
from tests.support.builders import (
    FILE_RULE,
    build_audit_command_app,
    make_settings,
    write_json,
    write_text,
)
from tests.support.fakes import FakeJudge

Capture = pytest.CaptureFixture[str]

SHAPES_SOURCE = """import functools


def traced(func):
    @functools.wraps(func)
    def wrapper(*args):
        return func(*args)

    return wrapper


class Cart:
    @property
    def total(self) -> int:
        return self._total

    @total.setter
    def total(self, value: int) -> None:
        self._total = value

    def size(self) -> int: return 0

    class Line:
        async def fetch(self) -> None:
            await self.client.get()


@traced
async def checkout() -> None:
    pass


if functools:
    def fallback() -> None:
        \"\"\"Do nothing.\"\"\"
"""


def _build_settings(tmp_path: Path) -> AppSettings:
    """Return settings with one rule for each class and one for each function."""
    pack = write_json(
        tmp_path / "rules.json",
        {
            "focused_class": {**FILE_RULE, "unit_types": ["class"]},
            "short_function": {**FILE_RULE, "unit_types": ["function"]},
        },
    )
    return make_settings(built_in_rule_packs=[pack])


@dataclass(frozen=True)
class _AuditResult:
    """The judge an audit asked, and where each unit it reported on sits."""

    judge: FakeJudge
    unit_id_to_location: dict[str, Location]


def _audit(tmp_path: Path, target: Path, capsys: Capture) -> _AuditResult:
    """Audit ``target`` with every answer shown."""
    judge = FakeJudge()
    app = build_audit_command_app(FILE_AUDIT_COMMAND, judge, _build_settings(tmp_path))
    asyncio.run(app.run([str(target), "--json", "--all-answers"]))
    output: dict[str, Any] = json.loads(capsys.readouterr().out)
    return _AuditResult(
        judge=judge,
        unit_id_to_location={
            finding["unit_id"]: Location(**finding["location"])
            for finding in output["findings"]
        },
    )


def test_each_class_method_and_function_is_a_unit_with_its_decorators(
    tmp_path: Path, capsys: Capture
) -> None:
    shapes = write_text(tmp_path / "shapes.py", SHAPES_SOURCE)

    result = _audit(tmp_path, shapes, capsys)

    path = str(shapes)
    # A nested function is part of its function; a property and its setter
    # share a name, so each is told apart by its first line; a function
    # defined in an if statement is a unit as well.
    assert result.unit_id_to_location == {
        f"{path}::traced": Location(path, 4, 9),
        f"{path}::Cart": Location(path, 12, 25),
        f"{path}::Cart.total:13": Location(path, 13, 15),
        f"{path}::Cart.total:17": Location(path, 17, 19),
        f"{path}::Cart.size": Location(path, 21, 21),
        f"{path}::Cart.Line": Location(path, 23, 25),
        f"{path}::Cart.Line.fetch": Location(path, 24, 25),
        f"{path}::checkout": Location(path, 28, 30),
        f"{path}::fallback": Location(path, 34, 35),
    }
    subjects = result.judge.map_subject_to_asked_rule_ids()
    assert "@traced\nasync def checkout() -> None:\n    pass" in subjects
    assert "@functools.wraps(func)\n    def wrapper(*args):" in next(
        subject for subject in subjects if subject.startswith("def traced")
    )


def test_class_shows_methods_of_its_own_classes_without_bodies(
    tmp_path: Path, capsys: Capture
) -> None:
    shapes = write_text(tmp_path / "shapes.py", SHAPES_SOURCE)

    result = _audit(tmp_path, shapes, capsys)

    # A method written on one line is shown whole: its body shares the line.
    assert """class Cart:
    @property
    def total(self) -> int:
        ...

    @total.setter
    def total(self, value: int) -> None:
        ...

    def size(self) -> int: return 0

    class Line:
        async def fetch(self) -> None:
            ...""" in result.judge.map_subject_to_asked_rule_ids()


def test_function_over_the_character_budget_is_shown_from_its_first_line(
    tmp_path: Path, capsys: Capture
) -> None:
    body = "".join(f"    step_{index} = {index}\n" for index in range(200))
    long_file = write_text(tmp_path / "long.py", f"def long() -> None:\n{body}")

    result = _audit(tmp_path, long_file, capsys)

    [subject] = result.judge.map_subject_to_asked_rule_ids()
    assert len(subject) <= DEFAULT_CHARACTER_BUDGET
    assert subject.startswith("def long() -> None:\n    step_0 = 0\n")
    assert subject.endswith(
        f"more lines of the function left out to stay within "
        f"{DEFAULT_CHARACTER_BUDGET} characters]"
    )
    assert result.unit_id_to_location == {
        f"{long_file}::long": Location(str(long_file), 1, 201)
    }


@pytest.mark.parametrize(
    "line_break", ["\r\n", "\r"], ids=["windows_line_breaks", "old_mac_line_breaks"]
)
def test_lines_are_counted_by_the_line_breaks_python_reads(
    tmp_path: Path, capsys: Capture, line_break: str
) -> None:
    # A form feed between functions is no line break to Python.
    source = "\f\ndef first() -> int:\n    return 1\n\ndef second() -> int:\n"
    source += "    return 2\n"
    target = tmp_path / "breaks.py"
    target.write_bytes(source.replace("\n", line_break).encode("utf-8"))

    result = _audit(tmp_path, target, capsys)

    path = str(target)
    assert result.unit_id_to_location == {
        f"{path}::first": Location(path, 2, 3),
        f"{path}::second": Location(path, 5, 6),
    }
    subjects = result.judge.map_subject_to_asked_rule_ids()
    assert "def second() -> int:\n    return 2" in subjects


def test_parser_warnings_about_the_audited_code_are_not_shown(
    tmp_path: Path, capsys: Capture, recwarn: pytest.WarningsRecorder
) -> None:
    target = write_text(
        tmp_path / "pattern.py",
        'import re\n\n\ndef digits():\n    return re.compile("\\d+")\n',
    )

    result = _audit(tmp_path, target, capsys)

    assert list(result.unit_id_to_location) == [f"{target}::digits"]
    assert [str(warning.message) for warning in recwarn] == []
