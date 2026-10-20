from dataclasses import asdict, dataclass, field

from klint.core.models.json_value import JsonValue
from klint.core.models.location import Location
from klint.core.models.scale import Choice
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
    answer: Choice
    question: str
    confidence: float | None = None
    choice_key_to_probability: dict[str, float] | None = None
    tags: tuple[str, ...] = ()
    location: Location | None = None
    evidence_location: Location | None = None
    context: UnitContext = field(default_factory=UnitContext)

    def is_failure(self) -> bool:
        return self.answer.is_finding

    def meets_confidence(self, min_confidence: float = 0.0) -> bool:
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

    def get_findings(
        self, fails_only: bool = True, min_confidence: float = 0.0
    ) -> list[AuditFinding]:
        """Return the selected findings, unit by unit, most important first.

        The units keep the order in which their findings were recorded.
        """
        unit_id_to_rank = {
            unit_id: rank
            for rank, unit_id in enumerate(
                dict.fromkeys(finding.unit_id for finding in self._findings)
            )
        }
        selected = [
            f
            for f in self._findings
            if (not fails_only or f.is_failure()) and f.meets_confidence(min_confidence)
        ]
        selected.sort(
            key=lambda f: (
                unit_id_to_rank[f.unit_id],
                f.answer.priority,
                -(f.confidence if f.confidence is not None else -1.0),
                f.rule_id,
            )
        )
        return selected

    def get_issues(
        self, fails_only: bool = True, min_confidence: float = 0.0
    ) -> list[dict[str, JsonValue]]:
        return [
            f.convert_to_dict() for f in self.get_findings(fails_only, min_confidence)
        ]
