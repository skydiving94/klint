"""Reads one rules file into typed values, checking the shape of each rule."""

import json
import warnings
from pathlib import Path
from typing import TypeGuard

from klint.core.klint_warning import KlintWarning
from klint.core.models.question_type import QuestionType
from klint.core.models.rule import DEFAULT_TARGET_UNIT_TYPES
from klint.core.models.rule_pack import (
    PackScope,
    RulePackSpec,
    RuleProblem,
    RuleProblemSeverity,
    RuleSpec,
)

RULE_FIELD_NAMES = frozenset(
    {"type", "instructions", "target_unit_types", "languages", "tags"}
)
# The header of a pack: which files the pack is for.
HEADER_KEY = "applies_to"
_HEADER_FIELD_NAMES = frozenset({"languages"})


def read_rule_pack(path: Path) -> RulePackSpec:
    """Read the rules file at ``path``.

    Raises ValueError naming the file when it is not a JSON object or its
    header is malformed; an unknown header field is reported as a
    KlintWarning. A rule with a field of the wrong kind is an ERROR problem.
    A rule without a type or instructions, and an unknown rule field, are
    WARNING problems.
    """
    try:
        raw_data: object = json.loads(path.read_text(encoding="utf-8"))
    except ValueError as error:
        raise ValueError(f"Rules file '{path}' is not valid JSON: {error}") from error
    if not isinstance(raw_data, dict):
        raise ValueError(f"Rules file '{path}' must be a JSON object")
    scope = (
        _read_scope(raw_data[HEADER_KEY], path)
        if HEADER_KEY in raw_data
        else PackScope()
    )
    rules: list[RuleSpec] = []
    rule_problems: list[RuleProblem] = []
    for rule_id, raw_rule in _select_raw_rules(raw_data).items():
        rule = _read_rule(str(rule_id), raw_rule, path, rule_problems)
        if rule is not None:
            rules.append(rule)
    return RulePackSpec(
        origin=str(path),
        scope=scope,
        rules=tuple(rules),
        rule_problems=tuple(rule_problems),
    )


def _select_raw_rules(raw_data: dict[object, object]) -> dict[object, object]:
    """Return the entries of the file that are rules.

    In a file with a "rules" object, the rules are its entries and the other
    keys belong to whatever else reads the file. In a flat file, every key
    but the header is a rule.
    """
    raw_rules = raw_data.get("rules")
    if isinstance(raw_rules, dict) and "type" not in raw_rules:
        return raw_rules
    return {key: value for key, value in raw_data.items() if key != HEADER_KEY}


def _read_scope(raw_header: object, path: Path) -> PackScope:
    """Return the scope an applies_to header states; raise if it is malformed."""
    if not isinstance(raw_header, dict):
        raise ValueError(
            f"Rules file '{path}' has an invalid {HEADER_KEY} header "
            f"{raw_header!r}; expected an object"
        )
    unknown_fields = sorted(str(key) for key in set(raw_header) - _HEADER_FIELD_NAMES)
    if unknown_fields:
        warnings.warn(
            f"The {HEADER_KEY} header in '{path}' has unknown fields "
            f"{unknown_fields}, which are ignored; known fields: "
            f"{sorted(_HEADER_FIELD_NAMES)}",
            KlintWarning,
            stacklevel=2,
        )
    if "languages" not in raw_header:
        return PackScope()
    raw_languages = raw_header["languages"]
    if not raw_languages or not _is_list_of_strings(raw_languages):
        raise ValueError(
            f"Rules file '{path}' has an invalid {HEADER_KEY} header: "
            f"languages {raw_languages!r} must be a non-empty list of strings"
        )
    return PackScope(languages=tuple(raw_languages))


def _read_rule(
    rule_id: str, raw_rule: object, path: Path, rule_problems: list[RuleProblem]
) -> RuleSpec | None:
    """Return the rule ``rule_id`` as written; None when it cannot be a rule.

    Each problem found is added to ``rule_problems``.
    """
    if (
        not isinstance(raw_rule, dict)
        or "type" not in raw_rule
        or "instructions" not in raw_rule
    ):
        rule_problems.append(
            RuleProblem(
                RuleProblemSeverity.WARNING,
                f"Rule '{rule_id}' in '{path}' is skipped: it needs both "
                "'type' and 'instructions'",
            )
        )
        return None
    unknown_fields = sorted(str(key) for key in set(raw_rule) - RULE_FIELD_NAMES)
    if unknown_fields:
        rule_problems.append(
            RuleProblem(
                RuleProblemSeverity.WARNING,
                f"Rule '{rule_id}' in '{path}' has unknown fields {unknown_fields}, "
                f"which are ignored; known fields: {sorted(RULE_FIELD_NAMES)}",
            )
        )
    try:
        return RuleSpec(
            rule_id=rule_id,
            question_type=_read_question_type(raw_rule["type"], rule_id, path),
            instructions=_read_instructions(raw_rule["instructions"], rule_id, path),
            target_unit_types=(
                _read_string_list(raw_rule, "target_unit_types", rule_id, path)
                if "target_unit_types" in raw_rule
                else DEFAULT_TARGET_UNIT_TYPES
            ),
            languages=_read_string_list(raw_rule, "languages", rule_id, path),
            tags=_read_string_list(raw_rule, "tags", rule_id, path),
        )
    except ValueError as error:
        rule_problems.append(RuleProblem(RuleProblemSeverity.ERROR, str(error)))
        return None


def _read_instructions(raw_instructions: object, rule_id: str, path: Path) -> str:
    if not isinstance(raw_instructions, str):
        raise ValueError(
            f"Rule '{rule_id}' has invalid instructions {raw_instructions!r} in "
            f"'{path}'; expected a string"
        )
    return raw_instructions


def _read_question_type(raw_type: object, rule_id: str, path: Path) -> QuestionType:
    for question_type in QuestionType:
        if raw_type == question_type.value:
            return question_type
    raise ValueError(
        f"Rule '{rule_id}' has unknown type {raw_type!r} in '{path}'; "
        f"known types: {[question_type.value for question_type in QuestionType]}"
    )


def _read_string_list(
    raw_rule: dict[object, object], field_name: str, rule_id: str, path: Path
) -> tuple[str, ...]:
    """Return the list of strings in ``field_name``; empty when it is absent."""
    if field_name not in raw_rule:
        return ()
    raw_value = raw_rule[field_name]
    if not _is_list_of_strings(raw_value):
        raise ValueError(
            f"Rule '{rule_id}' has invalid {field_name} {raw_value!r} in "
            f"'{path}'; expected a list of strings"
        )
    return tuple(raw_value)


def _is_list_of_strings(raw_value: object) -> TypeGuard[list[str]]:
    return isinstance(raw_value, list) and all(
        isinstance(item, str) for item in raw_value
    )
