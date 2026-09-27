from dataclasses import asdict, dataclass, field
from typing import Any, ClassVar, Dict, List

from src.core.domain.units.base import AuditableUnit


@dataclass(frozen=True)
class FileMetadataPayload:
    file_name: str = ""
    file_path: str = ""
    line_count: int = 0
    imports: List[str] = field(default_factory=list)
    exports: List[str] = field(default_factory=list)
    classes: List[str] = field(default_factory=list)
    functions: List[str] = field(default_factory=list)


@dataclass(frozen=True)
class AuditableFileMetadataUnit(AuditableUnit):
    """Auditable unit representing extracted structural metadata of a single file."""

    unit_type: ClassVar[str] = "file_metadata"

    file_name: str = ""
    file_path: str = ""
    line_count: int = 0
    imports: List[str] = field(default_factory=list)
    exports: List[str] = field(default_factory=list)
    classes: List[str] = field(default_factory=list)
    functions: List[str] = field(default_factory=list)

    def get_content(self) -> str:
        details: List[str] = [f"lines={self.line_count}"]
        if self.exports:
            details.append(f"exports=[{', '.join(self.exports)}]")
        if self.imports:
            details.append(f"imports=[{', '.join(self.imports)}]")
        if self.classes:
            details.append(f"classes=[{', '.join(self.classes)}]")
        if self.functions:
            details.append(f"functions=[{', '.join(self.functions)}]")
        return f"{self.file_name} ({'; '.join(details)})"

    def get_metadata(self) -> Dict[str, Any]:
        payload = FileMetadataPayload(
            file_name=self.file_name,
            file_path=self.file_path,
            line_count=self.line_count,
            imports=list(self.imports),
            exports=list(self.exports),
            classes=list(self.classes),
            functions=list(self.functions),
        )
        return asdict(payload)
