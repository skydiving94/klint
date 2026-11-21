"""What tells one finding on one version of a unit's code from every other."""

import hashlib
from dataclasses import dataclass
from pathlib import Path

from klint.core.models.reports import AuditFinding
from klint.core.models.units import Location

_HASH_PREFIX = "sha256:"
# The length of an entry ID: 12 hexadecimal digits, short enough to type.
_ENTRY_ID_LENGTH = 12


@dataclass(frozen=True)
class FindingIdentity:
    """A rule's finding on one version of a unit's code.

    file is the unit's file, relative to the repository's root, and
    unit_name what the unit is reached by inside its file; the file unit
    has the empty name. code_hash is the hash of the unit's code. Two
    findings with the same identity are the same finding, so an
    acknowledgement of one covers the other.
    """

    rule_id: str
    file: str
    unit_name: str
    code_hash: str

    def build_entry_id(self) -> str:
        """Return the ID of this finding's log entry: the same identity, the same ID."""
        text = "\n".join((self.rule_id, self.file, self.unit_name, self.code_hash))
        return hashlib.sha256(text.encode("utf-8")).hexdigest()[:_ENTRY_ID_LENGTH]


def identify_finding(
    finding: AuditFinding, repository_root: Path, working_directory: Path
) -> FindingIdentity | None:
    """Return the identity of ``finding``, whose paths are from ``working_directory``.

    The unit's code is read from its file on disk. None when the finding has
    no location, its file is outside the repository, or cannot be read.
    """
    if finding.location is None:
        return None
    return identify_unit_finding(
        finding.rule_id,
        finding.unit_id,
        finding.location,
        repository_root,
        working_directory,
    )


def identify_unit_finding(
    rule_id: str,
    unit_id: str,
    location: Location,
    repository_root: Path,
    working_directory: Path,
) -> FindingIdentity | None:
    """Return the identity of a finding of ``rule_id`` on the unit at ``location``.

    The location's path is from ``working_directory``, and the unit's code is
    read from its file on disk. None when the file is outside the repository
    or cannot be read, as for a directory.
    """
    file = relate_path_to_repository(location.path, repository_root, working_directory)
    if file is None:
        return None
    try:
        code = read_unit_code(
            working_directory / location.path, location.start_line, location.end_line
        )
    except OSError:
        return None
    return FindingIdentity(
        rule_id=rule_id,
        file=file,
        unit_name=describe_unit_name(unit_id, location.path),
        code_hash=hash_code(code),
    )


def relate_path_to_repository(
    path: str, repository_root: Path, working_directory: Path
) -> str | None:
    """Return ``path``, given from ``working_directory``, from the repository's root.

    The path is written with "/" whatever the platform. None when the path
    is outside the repository.
    """
    try:
        relative_path = (
            (working_directory / path).resolve().relative_to(repository_root.resolve())
        )
    except ValueError:
        return None
    return relative_path.as_posix()


def describe_unit_name(unit_id: str, path: str) -> str:
    """Return what the unit ``unit_id`` is reached by inside its file at ``path``.

    A unit's ID is its file's path, then "::" and its name; the file unit's
    ID is the path alone, and its name is empty.
    """
    return unit_id.removeprefix(path).removeprefix("::")


def read_unit_code(path: Path, start_line: int | None, end_line: int | None) -> str:
    """Return the lines ``start_line`` to ``end_line`` of the file at ``path``.

    The whole file when either line is unknown. Raises OSError when the file
    cannot be read.
    """
    text = path.read_text(encoding="utf-8", errors="replace")
    if start_line is None or end_line is None:
        return text
    return "".join(text.splitlines(keepends=True)[start_line - 1 : end_line])


def hash_code(code: str) -> str:
    """Return the hash of ``code`` as the log records it."""
    return _HASH_PREFIX + hashlib.sha256(code.encode("utf-8")).hexdigest()
