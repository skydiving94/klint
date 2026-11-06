"""The accuracy test set for change summaries: true summaries and planted mistakes.

The set is a folder of case files, one per commit. A case file holds a
change-summary document whose every summary is true, under "true_document",
and the mistakes planted in it, under "planted_mistakes": each one replaces
one summary of the document with a wrong one.
"""

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from judge_accuracy.change_summary.summary_pointer import find_summary, replace_summary
from klint.core.models.reports import JsonValue

# The one version of the case file format there is.
SUPPORTED_SCHEMA_VERSION = 1
_CASE_FILE_GLOB = "*.json"


class MistakeKind(StrEnum):
    """The kind of mistake a planted summary makes.

    FALSE_STATEMENT: it says what its evidence shows is not so.
    UNSUPPORTED_REASON: it gives a reason, goal or benefit its evidence
    does not state. CONTRADICTION: it disagrees with a summary one level
    down; only a file, package or commit summary has one. OMISSION: it
    leaves out a change its evidence shows.
    """

    FALSE_STATEMENT = "false_statement"
    UNSUPPORTED_REASON = "unsupported_reason"
    CONTRADICTION = "contradiction"
    OMISSION = "omission"


@dataclass(frozen=True)
class PlantedMistake:
    """One summary of a document, replaced by a wrong one.

    summary_pointer is where the summary sits, as a finding's location
    gives it, such as "#/files/0/hunks/2/summary". summary is the wrong
    summary, mistake_kind the kind of mistake it makes, and why_wrong what
    is wrong with it.
    """

    summary_pointer: str
    mistake_kind: MistakeKind
    summary: str
    why_wrong: str


@dataclass(frozen=True)
class CaseFile:
    """A document of true summaries and the mistakes planted in it.

    name is the case file's name without its extension.
    """

    name: str
    true_document: JsonValue
    planted_mistakes: tuple[PlantedMistake, ...]

    def build_planted_document(self, mistake: PlantedMistake) -> JsonValue:
        """Return the true document with ``mistake``'s summary in place."""
        return replace_summary(
            self.true_document, mistake.summary_pointer, mistake.summary
        )


def read_case_set(folder: Path) -> list[CaseFile]:
    """Return the case files in ``folder``, in name order.

    Raises OSError when the folder or a file cannot be read, and ValueError
    when the folder holds no case file or a file is not a valid case file.
    """
    paths = sorted(folder.glob(_CASE_FILE_GLOB))
    if not paths:
        raise ValueError(f"{folder} holds no case file ({_CASE_FILE_GLOB})")
    return [read_case_file(path) for path in paths]


def read_case_file(path: Path) -> CaseFile:
    """Return the case file at ``path``.

    Raises OSError when it cannot be read, and ValueError when it is not
    JSON or not a valid case file.
    """
    try:
        data: JsonValue = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise ValueError(f"{path} is not JSON: {error}") from error
    try:
        return _build_case_file(path.stem, data)
    except ValueError as error:
        raise ValueError(f"{path}: {error}") from error


def _build_case_file(name: str, data: JsonValue) -> CaseFile:
    fields = _require_mapping(data, "the case file")
    if fields.get("schema_version") != SUPPORTED_SCHEMA_VERSION:
        raise ValueError(
            f"schema_version is {fields.get('schema_version')!r}; only "
            f"{SUPPORTED_SCHEMA_VERSION} is read"
        )
    true_document = fields.get("true_document")
    _require_mapping(true_document, "true_document")
    mistakes = tuple(
        _build_planted_mistake(true_document, entry, index)
        for index, entry in enumerate(
            _require_list(fields.get("planted_mistakes"), "planted_mistakes")
        )
    )
    _check_mistakes_differ(mistakes)
    return CaseFile(name=name, true_document=true_document, planted_mistakes=mistakes)


def _build_planted_mistake(
    true_document: JsonValue, entry: JsonValue, index: int
) -> PlantedMistake:
    where = f"planted_mistakes/{index}"
    fields = _require_mapping(entry, where)
    pointer = _require_text(fields.get("summary_pointer"), f"{where}/summary_pointer")
    summary = _require_text(fields.get("summary"), f"{where}/summary")
    kind_name = _require_text(fields.get("mistake_kind"), f"{where}/mistake_kind")
    try:
        mistake_kind = MistakeKind(kind_name)
    except ValueError:
        raise ValueError(
            f"{where}/mistake_kind {kind_name!r} is not one of "
            f"{[kind.value for kind in MistakeKind]}"
        ) from None
    try:
        true_summary = find_summary(true_document, pointer)
    except ValueError as error:
        raise ValueError(f"{where}/summary_pointer: {error}") from error
    if summary == true_summary:
        raise ValueError(f"{where}/summary is the true summary itself")
    return PlantedMistake(
        summary_pointer=pointer,
        mistake_kind=mistake_kind,
        summary=summary,
        why_wrong=_require_text(fields.get("why_wrong"), f"{where}/why_wrong"),
    )


def _check_mistakes_differ(mistakes: Sequence[PlantedMistake]) -> None:
    """Raise ValueError when two planted mistakes put the same summary in one place."""
    seen: set[tuple[str, str]] = set()
    for mistake in mistakes:
        key = (mistake.summary_pointer, mistake.summary)
        if key in seen:
            raise ValueError(
                f"{mistake.summary_pointer} is given the same planted summary twice"
            )
        seen.add(key)


def _require_mapping(value: JsonValue, what: str) -> Mapping[str, JsonValue]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{what} is not a JSON object")
    return value


def _require_list(value: JsonValue, what: str) -> Sequence[JsonValue]:
    if not isinstance(value, list):
        raise ValueError(f"{what} is not a JSON list")
    return value


def _require_text(value: JsonValue, what: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{what} is not a non-empty string")
    return value
