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

    line_count is None for a binary file, whose content is not read: such a
    file is described by its name only. is_unparseable is True for a file the
    parser gave up on: its imports, exports, classes and functions are
    unknown, not empty, and it is described by its name and line count.
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

    def get_content(self) -> str:
        if self.line_count is None:
            return f"{self.file_name} (binary)"
        details: list[str] = [f"lines={self.line_count}"]
        if self.is_unparseable:
            details.append("cannot be parsed")
        if self.exports:
            details.append(f"exports=[{', '.join(self.exports)}]")
        if self.imports:
            details.append(f"imports=[{', '.join(self.imports)}]")
        if self.classes:
            details.append(f"classes=[{', '.join(self.classes)}]")
        if self.functions:
            details.append(f"functions=[{', '.join(self.functions)}]")
        return f"{self.file_name} ({'; '.join(details)})"

    def get_location(self) -> Location | None:
        return Location(source=self.file_path or self.unit_id)

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
