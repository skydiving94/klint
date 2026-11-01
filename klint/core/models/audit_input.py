"""What an audit is asked to go through, as the caller hands it over."""

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import ClassVar, TypeAlias


class AuditInputKind(Enum):
    """The forms an audit input can come in."""

    DISK_PATH = "disk_path"
    IN_MEMORY_BYTES = "in_memory_bytes"


@dataclass(frozen=True)
class DiskPathInput:
    """A file or directory on disk, at ``path``."""

    input_kind: ClassVar[AuditInputKind] = AuditInputKind.DISK_PATH

    path: Path


@dataclass(frozen=True)
class InMemoryBytesInput:
    """Content held in memory, with no file behind it.

    media_type says what the content is, such as "application/json".
    """

    input_kind: ClassVar[AuditInputKind] = AuditInputKind.IN_MEMORY_BYTES

    content: bytes
    media_type: str


AuditInput: TypeAlias = DiskPathInput | InMemoryBytesInput
