from abc import ABC, abstractmethod
from pathlib import Path

from klint.catalog.code.language_neutral.units.directory_unit import (
    AuditableDirectoryUnit,
)
from klint.catalog.code.language_neutral.units.file_metadata_unit import (
    AuditableFileMetadataUnit,
)


class BaseDirectoryUnitFactory(ABC):
    """Turns a walked directory into the unit that describes it."""

    @abstractmethod
    def build(
        self,
        directory_path: Path,
        files: list[AuditableFileMetadataUnit],
        subdirectories: list[AuditableDirectoryUnit],
        language: str | None,
    ) -> AuditableDirectoryUnit:
        """Return the unit for one directory whose contents are already built.

        ``language`` is the language the directory is described in, or None
        when it is described in a language-neutral way.
        """

    def update_units_after_full_walk(
        self, root_unit: AuditableDirectoryUnit
    ) -> AuditableDirectoryUnit:
        """Return the tree with any change that had to wait for the whole walk.

        Called once, with the root of the finished tree, after every
        directory has been built.
        """
        return root_unit
