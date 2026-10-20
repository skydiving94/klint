from dataclasses import dataclass
from typing import ClassVar

from klint.core.models.location import Location
from klint.core.models.unit import AuditableUnit


@dataclass(frozen=True)
class AuditableFileUnit(AuditableUnit):
    """Concrete auditable unit representing an entire source file."""

    unit_type: ClassVar[str] = "file"

    content: str = ""
    file_path: str | None = None
    start_line: int | None = None
    end_line: int | None = None

    def get_content(self) -> str:
        return self.content

    def get_location(self) -> Location | None:
        return Location(
            source=self.file_path or self.unit_id,
            start_line=self.start_line,
            end_line=self.end_line,
        )
