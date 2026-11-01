from dataclasses import dataclass, field
from typing import ClassVar

from klint.core.models.location import Location
from klint.core.models.unit import AuditableUnit, UnitContext


@dataclass(frozen=True)
class FileMetadataContext(UnitContext):
    """What was read from a file without judging it; see AuditableFileMetadataUnit."""

    file_name: str = ""
    line_count: int | None = 0
    imports: list[str] = field(default_factory=list)
    exports: list[str] = field(default_factory=list)
    classes: list[str] = field(default_factory=list)
    functions: list[str] = field(default_factory=list)
    is_unparseable: bool = False


@dataclass(frozen=True)
class AuditableFileMetadataUnit(AuditableUnit):
    """Auditable unit representing extracted structural metadata of a single file.

    line_count is None for a binary file, whose content is not read.
    is_unparseable is True for a file the parser gave up on: its imports,
    exports, classes and functions are unknown, not empty.
    """

    unit_type: ClassVar[str] = "file_metadata"

    file_name: str = ""
    file_path: str = ""
    line_count: int | None = 0
    imports: list[str] = field(default_factory=list)
    exports: list[str] = field(default_factory=list)
    classes: list[str] = field(default_factory=list)
    functions: list[str] = field(default_factory=list)
    is_unparseable: bool = False

    def get_location(self) -> Location | None:
        return Location(path=self.file_path or self.unit_id)

    def get_context(self) -> FileMetadataContext:
        return FileMetadataContext(
            file_name=self.file_name,
            line_count=self.line_count,
            imports=list(self.imports),
            exports=list(self.exports),
            classes=list(self.classes),
            functions=list(self.functions),
            is_unparseable=self.is_unparseable,
        )
