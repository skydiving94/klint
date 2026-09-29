from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from src.core.domain.enums import Judgment

_JUDGMENT_PRIORITY: Dict[Judgment, int] = {
    Judgment.FAIL: 0,
    Judgment.LACK_OF_EVIDENCE: 1,
    Judgment.PASS: 2,
    Judgment.IRRELEVANT: 3,
}


@dataclass(frozen=True)
class AuditFinding:
    rule_id: str
    unit_id: str
    judgment: Judgment
    instructions: str
    confidence: Optional[float] = None
    probabilities: Optional[Dict[str, float]] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def is_failure(self) -> bool:
        return self.judgment == Judgment.FAIL

    def meets_confidence(self, min_confidence: float = 0.0) -> bool:
        if self.confidence is None:
            return True
        return self.confidence >= min_confidence

    def to_dict(self) -> Dict[str, Any]:
        return {
            "rule_id": self.rule_id,
            "unit_id": self.unit_id,
            "judgment": self.judgment.value,
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

    def get_issues(
        self, fails_only: bool = True, min_confidence: float = 0.0
    ) -> List[Dict[str, Any]]:
        selected = [
            f
            for f in self._findings
            if (not fails_only or f.is_failure())
            and f.meets_confidence(min_confidence)
        ]
        selected.sort(
            key=lambda f: (
                _JUDGMENT_PRIORITY.get(f.judgment, 99),
                -(f.confidence if f.confidence is not None else -1.0),
                f.rule_id,
            )
        )
        return [f.to_dict() for f in selected]
