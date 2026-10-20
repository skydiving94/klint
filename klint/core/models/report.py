from dataclasses import asdict, dataclass, field

from klint.core.models.json_value import JsonValue
from klint.core.models.location import Location
from klint.core.models.scale import AnswerChoice
from klint.core.models.unit import UnitContext


@dataclass(frozen=True)
class AuditFinding:
    """The judge's answer to one rule about one unit.

    question is the rule's question as the judge was asked it, and tags are
    the rule's topic labels. location is where the unit, the claim judged,
    sits; evidence_location is where its evidence sits, when the unit has
    evidence apart from itself. context is what the unit tells beyond its
    ID and location.
    """

    rule_id: str
    unit_id: str
    answer: AnswerChoice
    question: str
    confidence: float | None = None
    choice_key_to_probability: dict[str, float] | None = None
    tags: tuple[str, ...] = ()
    location: Location | None = None
    evidence_location: Location | None = None
    context: UnitContext = field(default_factory=UnitContext)

    def is_problem(self) -> bool:
        """Return True when the answer counts as a problem on its scale."""
        return self.answer.is_problem

    def does_meet_confidence(self, min_confidence: float = 0.0) -> bool:
        if self.confidence is None:
            return True
        return self.confidence >= min_confidence

    def convert_to_dict(self) -> dict[str, JsonValue]:
        """Return the finding as written to JSON: the same keys for any unit."""
        return {
            "rule_id": self.rule_id,
            "unit_id": self.unit_id,
            "answer": self.answer.label,
            "confidence": self.confidence,
            "choice_key_to_probability": self.choice_key_to_probability,
            "question": self.question,
            "tags": list(self.tags),
            "location": _convert_location_to_dict(self.location),
            "evidence_location": _convert_location_to_dict(self.evidence_location),
            "context": asdict(self.context),
        }


def _convert_location_to_dict(location: Location | None) -> JsonValue:
    return None if location is None else asdict(location)


@dataclass
class AuditReport:
    """What an audit found: the units it audited and the findings on them."""

    _findings: list[AuditFinding] = field(default_factory=list)
    _audited_unit_ids: list[str] = field(default_factory=list)

    def record(self, finding: AuditFinding) -> None:
        self._findings.append(finding)

    def record_audited_unit(self, unit_id: str) -> None:
        """Take note that the unit ``unit_id`` was audited without error."""
        self._audited_unit_ids.append(unit_id)

    def audited_unit_ids(self) -> list[str]:
        """Return the IDs of the units audited without error, in recorded order."""
        return list(self._audited_unit_ids)

    def list_findings(self) -> list[AuditFinding]:
        """Return every finding, in recorded order."""
        return list(self._findings)

    def select_findings(
        self,
        *,
        should_include_non_problems: bool = False,
        min_confidence: float = 0.0,
    ) -> list[AuditFinding]:
        """Return the findings a report shows, in recorded order.

        Only problems are selected unless ``should_include_non_problems``,
        and only those with at least ``min_confidence``; a finding with no
        confidence is always kept.
        """
        return [
            finding
            for finding in self._findings
            if (should_include_non_problems or finding.is_problem())
            and finding.does_meet_confidence(min_confidence)
        ]
