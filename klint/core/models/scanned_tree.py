"""What a scan of an audit target found, as a tree of directories and files."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path

from klint.core.models.file_traits import FileTraits


@dataclass
class ScannedFile:
    """A file found by a scan, with the traits identified for it.

    parent is the directory the file was found in. It is None when the file
    itself was the target of the scan.
    """

    path: Path
    traits: FileTraits
    parent: ScannedDirectory | None = field(default=None, compare=False, repr=False)


@dataclass
class ScannedDirectory:
    """A directory found by a scan, with the entries directly inside it.

    parent is the directory this one was found in. It is None for the
    directory that was the target of the scan.
    """

    path: Path
    parent: ScannedDirectory | None = field(default=None, compare=False, repr=False)
    subdirectories: list[ScannedDirectory] = field(default_factory=list)
    files: list[ScannedFile] = field(default_factory=list)

    def yield_files(self) -> Iterator[ScannedFile]:
        """Yield every file in this directory's tree, in the order of their paths."""
        entries: list[ScannedFile | ScannedDirectory] = [
            *self.files,
            *self.subdirectories,
        ]
        for entry in sorted(entries, key=lambda entry: entry.path):
            if isinstance(entry, ScannedFile):
                yield entry
            else:
                yield from entry.yield_files()

    def yield_directories(self) -> Iterator[ScannedDirectory]:
        """Yield this directory, then every directory beneath it, in path order."""
        yield self
        for subdirectory in sorted(self.subdirectories, key=lambda entry: entry.path):
            yield from subdirectory.yield_directories()
