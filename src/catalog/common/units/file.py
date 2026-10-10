from dataclasses import asdict, dataclass
from typing import Any, ClassVar

from src.core.models.location import Location
from src.core.models.unit import AuditableUnit


@dataclass(frozen=True)
class FileUnitMetadata:
    file_path: str | None = None
    line_range: list[int] | None = None


@dataclass(frozen=True)
class AuditableFileUnit(AuditableUnit):
    """Concrete auditable unit representing an entire source file."""

    unit_type: ClassVar[str] = "file"

    content: str = ""
    file_path: str | None = None
    start_line: int | None = None
    end_line: int | None = None

    @property
    def line_range(self) -> tuple[int, int] | None:
        if self.start_line is not None and self.end_line is not None:
            return (self.start_line, self.end_line)
        return None

    def get_content(self) -> str:
        return self.content

    def get_location(self) -> Location | None:
        return Location(
            source=self.file_path or self.unit_id,
            start_line=self.start_line,
            end_line=self.end_line,
        )

    def get_metadata(self) -> dict[str, Any]:
        metadata = FileUnitMetadata(
            file_path=self.file_path,
            line_range=list(self.line_range) if self.line_range else None,
        )
        return asdict(metadata)
