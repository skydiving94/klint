"""Checks that the files on disk are the ones a diff's index lines name."""

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from klint.catalog.domain_neutral.git.git_change import ChangeKind, GitFileChange
from klint.catalog.domain_neutral.git.git_command import run_git_or_raise


@dataclass(frozen=True)
class BlobHashMismatch:
    """A file on disk that is not the one the diff changes.

    path is the file's path in the diff. expected_hash is the hash the diff
    names, and found_hash the file's, as git hashes it; None when the file
    is not on disk.
    """

    path: str
    expected_hash: str
    found_hash: str | None

    def describe(self) -> str:
        """Say how the file differs, such as "'a.py' hashes to 1a2b3c4, not 5d6e7f8"."""
        if self.found_hash is None:
            return f"'{self.path}' is not on disk"
        expected_length = len(self.expected_hash)
        return (
            f"'{self.path}' hashes to {self.found_hash[:expected_length]}, "
            f"not {self.expected_hash}"
        )


async def find_blob_hash_mismatches(
    files: Sequence[GitFileChange], directory: Path
) -> list[BlobHashMismatch]:
    """Return each file of ``files``, under ``directory``, unlike its diff's hash.

    A file is hashed as ``git hash-object`` hashes it in ``directory``, so
    with the filters of its repository, if any. A deleted file, and one
    the diff names no hash for, is not checked. Raises ValueError when git
    cannot be run.
    """
    expected = [
        BlobHashMismatch(file_change.path, file_change.new_blob_hash, None)
        for file_change in files
        if file_change.change_kind is not ChangeKind.DELETED
        and file_change.new_blob_hash is not None
    ]
    missing = [entry for entry in expected if not (directory / entry.path).is_file()]
    on_disk = [entry for entry in expected if entry not in missing]
    found_hashes = await _hash_files([entry.path for entry in on_disk], directory)
    mismatches = missing + [
        BlobHashMismatch(entry.path, entry.expected_hash, found_hash)
        for entry, found_hash in zip(on_disk, found_hashes, strict=True)
        if not found_hash.startswith(entry.expected_hash.lower())
    ]
    return sorted(mismatches, key=lambda mismatch: mismatch.path)


async def _hash_files(paths: Sequence[str], directory: Path) -> list[str]:
    """Return the hash git gives each file, in the order of ``paths``."""
    if not paths:
        return []
    output = await run_git_or_raise(
        ["hash-object", "--stdin-paths"],
        directory,
        stdin_text="".join(f"{path}\n" for path in paths),
    )
    return output.split()
