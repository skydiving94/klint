"""What an audit is asked to go through, as the caller hands it over."""

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import ClassVar, TypeAlias


class AuditInputKind(Enum):
    """The forms an audit input can come in."""

    DISK_PATH = "disk_path"
    DISK_FILE_SET = "disk_file_set"
    IN_MEMORY_BYTES = "in_memory_bytes"


@dataclass(frozen=True)
class DiskPathInput:
    """A file or directory on disk, at ``path``."""

    input_kind: ClassVar[AuditInputKind] = AuditInputKind.DISK_PATH

    path: Path


@dataclass(frozen=True)
class DiskFileSetInput:
    """Chosen files on disk, at ``paths``, beneath the directory ``root``.

    The files are audited as they are listed: nothing else beneath root is
    looked at. root is the directory the files are told apart from, as the
    target of a disk path is; each path is given as the audit should name
    the file, relative to the working directory or absolute.
    """

    input_kind: ClassVar[AuditInputKind] = AuditInputKind.DISK_FILE_SET

    root: Path
    paths: tuple[Path, ...]


@dataclass(frozen=True)
class InMemoryBytesInput:
    """Content held in memory, with no file behind it.

    media_type says what the content is, such as "application/json".
    """

    input_kind: ClassVar[AuditInputKind] = AuditInputKind.IN_MEMORY_BYTES

    content: bytes
    media_type: str


AuditInput: TypeAlias = DiskPathInput | DiskFileSetInput | InMemoryBytesInput
