from collections.abc import Sequence
from pathlib import Path

from klint.catalog.common.file_traits_identifiers.path_glob import (
    does_path_match_glob,
)
from klint.core.interfaces.file_traits_identifier import BaseFileTraitsIdentifier
from klint.core.models.file_traits_override import FileTraitsOverride
from klint.core.models.unit_traits import UnitTraits


class OverridingFileTraitsIdentifier(BaseFileTraitsIdentifier):
    """Lets a project's overrides win over the traits another identifier detects.

    The first override whose glob matches a file decides: its language
    replaces the detected one, and its tags replace every detected tag,
    those from the start of the file too. What it leaves unset stays as
    detected.
    """

    def __init__(
        self,
        detecting_identifier: BaseFileTraitsIdentifier,
        file_traits_overrides: Sequence[FileTraitsOverride],
    ) -> None:
        self._detecting_identifier = detecting_identifier
        self._file_traits_overrides = tuple(file_traits_overrides)

    def identify(self, path: str | Path, scan_root: Path | None = None) -> UnitTraits:
        traits = self._detecting_identifier.identify(path, scan_root)
        override = self._find_override(Path(path))
        if override is None:
            return traits
        return UnitTraits(
            language=traits.language
            if override.language is None
            else override.language,
            tags=traits.tags if override.tags is None else override.tags,
        )

    def identify_from_file_start(
        self, path: Path, traits: UnitTraits, file_start: str
    ) -> UnitTraits:
        override = self._find_override(path)
        if override is not None and override.tags is not None:
            return traits
        return self._detecting_identifier.identify_from_file_start(
            path, traits, file_start
        )

    def _find_override(self, path: Path) -> FileTraitsOverride | None:
        """Return the first override whose glob matches ``path``; None if none."""
        if not self._file_traits_overrides:
            return None
        resolved_path = path.resolve()
        for override in self._file_traits_overrides:
            try:
                path_in_project = resolved_path.relative_to(
                    override.base_directory.resolve()
                )
            except ValueError:
                continue
            if does_path_match_glob(path_in_project, override.glob):
                return override
        return None
