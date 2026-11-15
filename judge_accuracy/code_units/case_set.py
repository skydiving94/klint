"""The code-unit accuracy set: true Python modules and the problems planted in them.

The set is a folder of case modules. Each one is a Python file, every file,
class and function of which follows klint's code rules, beside a JSON file
of the same name that lists the problems planted in it. Each planted
problem replaces one piece of the module's text with a version that breaks
one rule.
"""

import ast
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from klint.core.models.reports import JsonValue

# The one version of the planted-problem file format there is.
SUPPORTED_SCHEMA_VERSION = 1
_CASE_MODULE_GLOB = "*.py"


@dataclass(frozen=True)
class PlantedProblem:
    """One piece of a module's text, replaced by one that breaks a rule.

    old_text occurs exactly once in the true module; new_text takes its
    place. rule_id is the rule the new text breaks, and why_wrong says how.
    """

    rule_id: str
    old_text: str
    new_text: str
    why_wrong: str


@dataclass(frozen=True)
class CaseModule:
    """A true Python module and the problems planted in it, one at a time.

    name is the module's file name without its extension.
    """

    name: str
    true_source: str
    planted_problems: tuple[PlantedProblem, ...]

    def build_planted_source(self, problem: PlantedProblem) -> str:
        """Return the true source with ``problem`` planted in it."""
        return self.true_source.replace(problem.old_text, problem.new_text, 1)


def read_case_set(folder: Path) -> list[CaseModule]:
    """Return the case modules of ``folder``, by file name.

    Raises OSError when the folder or a file cannot be read, and ValueError
    when the folder holds no case module, or one is not valid.
    """
    if not folder.is_dir():
        raise ValueError(f"{folder} is not a folder of case modules")
    paths = sorted(folder.glob(_CASE_MODULE_GLOB))
    if not paths:
        raise ValueError(f"{folder} holds no case module ({_CASE_MODULE_GLOB})")
    return [_read_case_module(path) for path in paths]


def _read_case_module(path: Path) -> CaseModule:
    true_source = path.read_text(encoding="utf-8")
    _check_parses(true_source, path.name)
    problems_path = path.with_suffix(".json")
    try:
        data: JsonValue = json.loads(problems_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise ValueError(f"{problems_path.name} is not valid JSON: {error}") from None
    case_module = CaseModule(
        name=path.stem,
        true_source=true_source,
        planted_problems=_read_planted_problems(data, problems_path.name),
    )
    for number, problem in enumerate(case_module.planted_problems, start=1):
        where = f"{problems_path.name}, planted problem {number}"
        occurrence_count = true_source.count(problem.old_text)
        if occurrence_count != 1:
            raise ValueError(
                f"{where}: old_text occurs {occurrence_count} times in "
                f"{path.name}, not once"
            )
        _check_parses(case_module.build_planted_source(problem), where)
    return case_module


def _read_planted_problems(
    data: JsonValue, file_name: str
) -> tuple[PlantedProblem, ...]:
    if not isinstance(data, Mapping):
        raise ValueError(f"{file_name} must hold a JSON object")
    schema_version = data.get("schema_version")
    if schema_version != SUPPORTED_SCHEMA_VERSION:
        raise ValueError(
            f"{file_name}: schema_version {schema_version!r} is not supported; "
            f"expected {SUPPORTED_SCHEMA_VERSION}"
        )
    problems = data.get("planted_problems")
    if not isinstance(problems, Sequence) or isinstance(problems, str):
        raise ValueError(f"{file_name}: planted_problems must be a list")
    return tuple(
        _read_planted_problem(problem, f"{file_name}, planted problem {number}")
        for number, problem in enumerate(problems, start=1)
    )


def _read_planted_problem(data: JsonValue, where: str) -> PlantedProblem:
    if not isinstance(data, Mapping):
        raise ValueError(f"{where} must be a JSON object")
    key_to_text: dict[str, str] = {}
    for key in ("rule_id", "old_text", "new_text", "why_wrong"):
        value = data.get(key)
        if not isinstance(value, str) or not value:
            raise ValueError(f"{where}: {key} must be a non-empty string")
        key_to_text[key] = value
    return PlantedProblem(**key_to_text)


def _check_parses(source: str, where: str) -> None:
    """Raise ValueError when ``source`` is not valid Python."""
    try:
        ast.parse(source)
    except SyntaxError as error:
        raise ValueError(f"{where} is not valid Python: {error}") from None
