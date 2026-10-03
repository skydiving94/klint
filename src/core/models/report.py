from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from src.core.models.location import Location
from src.core.models.scale import Choice


@dataclass(frozen=True)
class AuditFinding:
    rule_id: str
    unit_id: str
    choice: Choice
    instructions: str
    confidence: Optional[float] = None
    probabilities: Optional[Dict[str, float]] = None
    location: Optional[Location] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def is_failure(self) -> bool:
        return self.choice.is_finding

    def meets_confidence(self, min_confidence: float = 0.0) -> bool:
        if self.confidence is None:
            return True
        return self.confidence >= min_confidence

    def to_dict(self) -> Dict[str, Any]:
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
    _findings: List[AuditFinding] = field(default_factory=list)

    def record(self, finding: AuditFinding) -> None:
        self._findings.append(finding)

    def get_findings(
        self, fails_only: bool = True, min_confidence: float = 0.0
    ) -> List[AuditFinding]:
        """Return the selected findings, most important first."""
        selected = [
            f
            for f in self._findings
            if (not fails_only or f.is_failure())
            and f.meets_confidence(min_confidence)
        ]
        selected.sort(
            key=lambda f: (
                f.choice.priority,
                -(f.confidence if f.confidence is not None else -1.0),
                f.rule_id,
            )
        )
        return selected

    def get_issues(
        self, fails_only: bool = True, min_confidence: float = 0.0
    ) -> List[Dict[str, Any]]:
        return [f.to_dict() for f in self.get_findings(fails_only, min_confidence)]
