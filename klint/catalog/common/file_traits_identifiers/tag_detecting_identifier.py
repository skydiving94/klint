from pathlib import Path, PurePath

from klint.catalog.common.file_traits_identifiers.imports import (
    find_imported_modules,
)
from klint.catalog.common.file_traits_identifiers.path_glob import (
    does_path_match_glob,
)
from klint.core.interfaces.file_traits_identifier import BaseFileTraitsIdentifier
from klint.core.models.tag_detection_table import TagDetectionTable
from klint.core.models.unit_traits import UnitTraits


class TagDetectingFileTraitsIdentifier(BaseFileTraitsIdentifier):
    """Adds to the traits another identifier gives the tags a file's path shows.

    The tags are those of the file's extension and of every path glob its
    path matches, from the scanned target down, and, once the start of the
    file is read, of every module imported there. A file that shows none
    has no tags.
    """

    def __init__(
        self,
        language_identifier: BaseFileTraitsIdentifier,
        tag_detection_table: TagDetectionTable,
    ) -> None:
        self._language_identifier = language_identifier
        self._tag_detection_table = tag_detection_table

    def identify(self, path: str | Path, scan_root: Path | None = None) -> UnitTraits:
        traits = self._language_identifier.identify(path, scan_root)
        path_in_target = _find_path_in_target(Path(path), scan_root)
        tags = set(
            self._tag_detection_table.extension_to_tags.get(
                path_in_target.suffix.lower(), ()
            )
        )
        for glob, glob_tags in self._tag_detection_table.path_glob_to_tags.items():
            if does_path_match_glob(path_in_target, glob):
                tags.update(glob_tags)
        return UnitTraits(language=traits.language, tags=frozenset(tags))

    def identify_from_file_start(
        self, path: Path, traits: UnitTraits, file_start: str
    ) -> UnitTraits:
        del path
        import_tags = {
            tag
            for module in find_imported_modules(file_start)
            for tag in self._tag_detection_table.import_to_tags.get(module, ())
        }
        return UnitTraits(language=traits.language, tags=traits.tags | import_tags)


def _find_path_in_target(path: Path, scan_root: Path | None) -> PurePath:
    """Return ``path`` from ``scan_root`` down; as given without a root."""
    if scan_root is None:
        return path
    try:
        return path.relative_to(scan_root)
    except ValueError:
        return PurePath(path.name)
