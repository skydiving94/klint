from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple
from src.core.domain.enums import Judgment, UnitType


@dataclass(frozen=True)
class AuditableUnit:
    unit_id: str
    unit_type: UnitType
    content: str | Dict[str, Any]

    # FIXME: These fields may be too concrete for a generic ABC / Interface.
    #  Should probably be moved to a subclass in the next iteration.
    #  This class should expect a generic function for getting the content in a string
    #  which is then evaluated along side the audit rules.
    file_path: Optional[str] = None
    start_line: Optional[int] = None
    end_line: Optional[int] = None

    @property
    def line_range(self) -> Optional[Tuple[int, int]]:
        if self.start_line is not None and self.end_line is not None:
            return (self.start_line, self.end_line)
        return None


@dataclass(frozen=True)
class AuditRule:
    rule_id: str

    # FIXME: This should be probably an enum?
    question_type: str
    instructions: str
    criteria: Dict[str, str]
    target_unit_types: List[UnitType] = field(
        default_factory=lambda: list(UnitType))

    def is_applicable_to(self, unit: AuditableUnit) -> bool:
        return unit.unit_type in self.target_unit_types


@dataclass(frozen=True)
class AuditFinding:
    rule_id: str
    unit_id: str
    judgment: Judgment
    instructions: str
    file_path: Optional[str] = None

    # TODO: Future work.
    line_range: Optional[Tuple[int, int]] = None
    confidence: Optional[float] = None
    probabilities: Optional[Dict[str, float]] = None

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
            "file_path": self.file_path,
            "line_range": list(self.line_range) if self.line_range else None,
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
        return [f.to_dict() for f in selected]
