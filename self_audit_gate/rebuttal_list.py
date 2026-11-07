import json
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

_REBUTTAL_LINK_PREFIX = "https://github.com/"
_ENTRY_FIELD_NAMES = frozenset({"audit", "rule_id", "unit_id", "rebuttal"})


class Audit(Enum):
    """The audits of klint's own code that the gate reads."""

    STRUCTURE = "structure"
    FILE = "file"


class GateInputError(ValueError):
    """A report or the rebuttal list cannot be used."""


@dataclass(frozen=True)
class FindingKey:
    """What names one finding across runs: its audit, rule and unit."""

    audit: Audit
    rule_id: str
    unit_id: str


@dataclass(frozen=True)
class ListedRebuttal:
    """A finding judged not valid, and the link to the comment that says why."""

    key: FindingKey
    rebuttal_link: str


def read_rebuttal_list(path: Path) -> tuple[ListedRebuttal, ...]:
    """Read the rebuttal list at ``path``.

    Raises GateInputError naming the problem when the file is not a list of
    entries that each name an audit, a rule, a unit and a rebuttal link.
    """
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise GateInputError(f"cannot read the rebuttal list {path}: {error}") from None
    entries = document.get("rebuttals") if isinstance(document, dict) else None
    if not isinstance(entries, list):
        raise GateInputError(f"{path} must hold an object with a 'rebuttals' list")
    return tuple(
        _read_entry(entry, f"{path}, entry {number}")
        for number, entry in enumerate(entries, start=1)
    )


def _read_entry(entry: object, where: str) -> ListedRebuttal:
    if not isinstance(entry, dict) or set(entry) != _ENTRY_FIELD_NAMES:
        raise GateInputError(f"{where} must hold exactly {sorted(_ENTRY_FIELD_NAMES)}")
    values = {name: entry[name] for name in _ENTRY_FIELD_NAMES}
    if not all(isinstance(value, str) and value for value in values.values()):
        raise GateInputError(f"{where}: every field must be a non-empty string")
    try:
        audit = Audit(values["audit"])
    except ValueError:
        raise GateInputError(
            f"{where}: audit must be one of {[audit.value for audit in Audit]}"
        ) from None
    if not values["rebuttal"].startswith(_REBUTTAL_LINK_PREFIX):
        raise GateInputError(
            f"{where}: rebuttal must link to the comment, {_REBUTTAL_LINK_PREFIX}…"
        )
    return ListedRebuttal(
        key=FindingKey(
            audit=audit, rule_id=values["rule_id"], unit_id=values["unit_id"]
        ),
        rebuttal_link=values["rebuttal"],
    )
