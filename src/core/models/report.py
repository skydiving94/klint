from dataclasses import dataclass, field
from typing import Any

from src.core.models.location import Location
from src.core.models.scale import Choice


@dataclass(frozen=True)
class AuditFinding:
    rule_id: str
    unit_id: str
    choice: Choice
    instructions: str
    confidence: float | None = None
    probabilities: dict[str, float] | None = None
    location: Location | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def is_failure(self) -> bool:
        return self.choice.is_finding

    def meets_confidence(self, min_confidence: float = 0.0) -> bool:
        if self.confidence is None:
            return True
        return self.confidence >= min_confidence

    def to_dict(self) -> dict[str, Any]:
        return {
            "rule_id": self.rule_id,
            "unit_id": self.unit_id,
            "judgment": self.choice.label,
            "confidence": self.confidence,
            "probabilities": self.probabilities,
            "instructions": self.instructions,
            **self.metadata,
        }


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
                f.choice.priority,
                -(f.confidence if f.confidence is not None else -1.0),
                f.rule_id,
            )
        )
        return selected

    def get_issues(
        self, fails_only: bool = True, min_confidence: float = 0.0
    ) -> list[dict[str, Any]]:
        return [f.to_dict() for f in self.get_findings(fails_only, min_confidence)]
