"""Reads and writes the entry files of an acknowledgement log folder."""

from pathlib import Path

from klint.core.models.reports import AcknowledgementEntry
from klint.infra.acknowledgement_log.entry_json import (
    read_entry_text,
    write_entry_text,
)

_ENTRY_SUFFIX = ".json"


class FileAcknowledgementLog:
    """The log in one folder: an entry per file, named by the entry's ID.

    A folder that does not exist holds no entry; it is created when the
    first entry is written.
    """

    def __init__(self, folder: Path) -> None:
        self._folder = folder

    @property
    def folder(self) -> Path:
        return self._folder

    def locate_entry(self, entry_id: str) -> Path:
        """Return the file the entry ``entry_id`` is, or would be, kept in."""
        return self._folder / f"{entry_id}{_ENTRY_SUFFIX}"

    def list_entries(self) -> list[AcknowledgementEntry]:
        """Return every entry, in file name order.

        Raises ValueError naming the file when one cannot be read as an
        entry, or when its name does not match its ID.
        """
        if not self._folder.is_dir():
            return []
        return [
            self._read_entry(path)
            for path in sorted(self._folder.iterdir())
            if path.is_file() and path.suffix == _ENTRY_SUFFIX
        ]

    def find_entry(self, entry_id: str) -> AcknowledgementEntry | None:
        """Return the entry ``entry_id``; None when the log holds none by that ID.

        Raises ValueError naming the file when it cannot be read as an entry.
        """
        path = self.locate_entry(entry_id)
        if not path.is_file():
            return None
        return self._read_entry(path)

    def write_entry(self, entry: AcknowledgementEntry) -> Path:
        """Write ``entry`` to its file, replacing any there; return the file."""
        path = self.locate_entry(entry.entry_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(write_entry_text(entry), encoding="utf-8")
        return path

    def remove_entry(self, entry_id: str) -> Path:
        """Delete the file of the entry ``entry_id``, if there; return the file."""
        path = self.locate_entry(entry_id)
        path.unlink(missing_ok=True)
        return path

    def _read_entry(self, path: Path) -> AcknowledgementEntry:
        try:
            entry = read_entry_text(path.read_text(encoding="utf-8"))
        except ValueError as error:
            raise ValueError(
                f"The acknowledgement log entry '{path}' cannot be read: {error}"
            ) from error
        if entry.entry_id != path.stem:
            raise ValueError(
                f"The acknowledgement log entry '{path}' cannot be read: its 'id' "
                f"{entry.entry_id!r} does not match its file name"
            )
        return entry
