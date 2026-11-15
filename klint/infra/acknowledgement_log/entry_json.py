"""How an entry of the acknowledgement log is written to JSON and read back."""

import json

from klint.core.models.reports import (
    AcknowledgementEntry,
    AcknowledgementStatus,
    FlaggedFinding,
    FlaggedUnit,
)

JsonObject = dict[str, object]


def write_entry_text(entry: AcknowledgementEntry) -> str:
    """Return ``entry`` as the text of its file: the same entry gives the same text."""
    entry_object: JsonObject = {
        "id": entry.entry_id,
        "rule_id": entry.rule_id,
        "file": entry.unit.file,
        "unit": {
            "kind": entry.unit.kind,
            "name": entry.unit.name,
            "start_line": entry.unit.start_line,
            "end_line": entry.unit.end_line,
        },
        "code_hash": entry.code_hash,
        "finding": {
            "answer": entry.finding.answer,
            "question": entry.finding.question,
            "confidence": entry.finding.confidence,
        },
        "judge_model_version": entry.judge_model_version,
        "first_flagged_at": entry.first_flagged_at,
        "status": entry.status.value,
        "acknowledged_at": entry.acknowledged_at,
        "note": entry.note,
    }
    return json.dumps(entry_object, indent=2) + "\n"


def read_entry_text(text: str) -> AcknowledgementEntry:
    """Return the entry ``text`` holds. Raises ValueError saying what is wrong."""
    try:
        raw: object = json.loads(text)
    except ValueError as error:
        raise ValueError(f"not valid JSON: {error}") from error
    if not isinstance(raw, dict):
        raise ValueError("must be a JSON object")
    entry = _Reader(raw)
    entry_id = entry.read_string("id")
    rule_id = entry.read_string("rule_id")
    file = entry.read_string("file")
    unit = _Reader(entry.read_object("unit"), "unit.")
    finding = _Reader(entry.read_object("finding"), "finding.")
    status = entry.read_string("status")
    try:
        parsed_status = AcknowledgementStatus(status)
    except ValueError:
        raise ValueError(
            f"'status' must be one of {[s.value for s in AcknowledgementStatus]}, "
            f"not {status!r}"
        ) from None
    return AcknowledgementEntry(
        entry_id=entry_id,
        rule_id=rule_id,
        unit=FlaggedUnit(
            file=file,
            kind=unit.read_string("kind"),
            name=unit.read_string("name", may_be_empty=True),
            start_line=unit.read_optional_int("start_line"),
            end_line=unit.read_optional_int("end_line"),
        ),
        code_hash=entry.read_string("code_hash"),
        finding=FlaggedFinding(
            answer=finding.read_string("answer"),
            question=finding.read_string("question", may_be_empty=True),
            confidence=finding.read_optional_float("confidence"),
        ),
        judge_model_version=entry.read_optional_string("judge_model_version"),
        first_flagged_at=entry.read_string("first_flagged_at"),
        status=parsed_status,
        acknowledged_at=entry.read_optional_string("acknowledged_at"),
        note=entry.read_optional_string("note"),
    )


class _Reader:
    """Reads the fields of one JSON object, naming each one that is wrong."""

    def __init__(self, raw: dict[object, object], prefix: str = "") -> None:
        self._raw = raw
        self._prefix = prefix

    def _describe(self, key: str) -> str:
        return f"'{self._prefix}{key}'"

    def read_object(self, key: str) -> dict[object, object]:
        value = self._raw.get(key)
        if not isinstance(value, dict):
            raise ValueError(f"{self._describe(key)} must be a JSON object")
        return value

    def read_string(self, key: str, *, may_be_empty: bool = False) -> str:
        value = self._raw.get(key)
        if not isinstance(value, str) or (not value and not may_be_empty):
            raise ValueError(f"{self._describe(key)} must be a non-empty string")
        return value

    def read_optional_string(self, key: str) -> str | None:
        value = self._raw.get(key)
        if value is not None and not isinstance(value, str):
            raise ValueError(f"{self._describe(key)} must be a string or null")
        return value

    def read_optional_int(self, key: str) -> int | None:
        value = self._raw.get(key)
        if value is not None and (
            isinstance(value, bool) or not isinstance(value, int)
        ):
            raise ValueError(f"{self._describe(key)} must be a whole number or null")
        return value

    def read_optional_float(self, key: str) -> float | None:
        value = self._raw.get(key)
        if value is None:
            return None
        if isinstance(value, bool) or not isinstance(value, int | float):
            raise ValueError(f"{self._describe(key)} must be a number or null")
        return float(value)
