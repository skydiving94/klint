from dataclasses import asdict, dataclass
from typing import Any, ClassVar, Dict, List, Optional, Tuple

from src.core.domain.units.base import AuditableUnit


@dataclass(frozen=True)
class FileUnitMetadata:
    file_path: Optional[str] = None
    line_range: Optional[List[int]] = None


@dataclass(frozen=True)
class AuditableFileUnit(AuditableUnit):
    """Concrete auditable unit representing an entire source file."""

    unit_type: ClassVar[str] = "file"

    content: str = ""
    file_path: Optional[str] = None
    start_line: Optional[int] = None
    end_line: Optional[int] = None

    @property
    def line_range(self) -> Optional[Tuple[int, int]]:
        if self.start_line is not None and self.end_line is not None:
            return (self.start_line, self.end_line)
        return None

    def get_content(self) -> str:
        return self.content

    def get_metadata(self) -> Dict[str, Any]:
        metadata = FileUnitMetadata(
            file_path=self.file_path,
            line_range=list(self.line_range) if self.line_range else None,
        )
        return asdict(metadata)
