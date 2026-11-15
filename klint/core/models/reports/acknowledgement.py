"""One entry of a project's acknowledgement log."""

from dataclasses import dataclass, replace
from enum import StrEnum


class AcknowledgementStatus(StrEnum):
    """Whether a logged finding still stands, or was judged wrong by a person."""

    OPEN = "open"
    ACKNOWLEDGED = "acknowledged"


@dataclass(frozen=True)
class FlaggedUnit:
    """The unit a logged finding is on, as the log names it.

    file is the unit's file, relative to the repository's root. kind is the
    unit's type, such as "file" or "function". name is what the unit is
    reached by inside its file, such as "Cart.total"; the file unit itself
    has the empty name. start_line and end_line are the lines it spanned
    when it was flagged.
    """

    file: str
    kind: str
    name: str
    start_line: int | None
    end_line: int | None

    def describe(self) -> str:
        """Say where the unit is, such as "cart.py::Cart.total (lines 10-13)"."""
        text = self.file if not self.name else f"{self.file}::{self.name}"
        if self.start_line is not None and self.end_line is not None:
            text += f" (lines {self.start_line}-{self.end_line})"
        return text


@dataclass(frozen=True)
class FlaggedFinding:
    """What the judge found: its answer, the question it answered, its confidence."""

    answer: str
    question: str
    confidence: float | None


@dataclass(frozen=True)
class AcknowledgementEntry:
    """One finding on one version of a unit's code, and what was decided about it.

    entry_id names the entry, and its file in the log. rule_id is the rule
    that found it. code_hash is the hash of the unit's code when it was
    flagged: the finding matches the entry only while the code hashes the
    same. judge_model_version is the version of the judge that flagged it;
    None when the judge did not tell. first_flagged_at is when the entry was
    created. An ACKNOWLEDGED entry carries acknowledged_at and the note that
    says why the finding is wrong.
    """

    entry_id: str
    rule_id: str
    unit: FlaggedUnit
    code_hash: str
    finding: FlaggedFinding
    judge_model_version: str | None
    first_flagged_at: str
    status: AcknowledgementStatus
    acknowledged_at: str | None = None
    note: str | None = None

    def is_open(self) -> bool:
        return self.status is AcknowledgementStatus.OPEN

    def acknowledge(self, note: str, acknowledged_at: str) -> "AcknowledgementEntry":
        """Return this entry acknowledged with ``note`` at ``acknowledged_at``."""
        return replace(
            self,
            status=AcknowledgementStatus.ACKNOWLEDGED,
            acknowledged_at=acknowledged_at,
            note=note,
        )
