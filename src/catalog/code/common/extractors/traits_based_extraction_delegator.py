"""The one place that decides what extracts each file and directory of a project."""

from collections import Counter
from collections.abc import Iterator, Mapping, Sequence
from pathlib import Path

from src.catalog.code.common.extractors.directory_factory import (
    BaseDirectoryUnitFactory,
)
from src.catalog.code.common.extractors.file_metadata_base import (
    BaseFileMetadataExtractor,
)
from src.catalog.code.common.extractors.language_neutral_directory_factory import (
    LanguageNeutralDirectoryUnitFactory,
)
from src.catalog.code.common.extractors.language_neutral_file_metadata import (
    LanguageNeutralFileMetadataExtractor,
)
from src.catalog.code.common.units.directory import AuditableDirectoryUnit
from src.catalog.code.common.units.file_metadata import AuditableFileMetadataUnit
from src.core.interfaces.file_traits_identifier import BaseFileTraitsIdentifier


class TraitsBasedExtractionDelegator:
    """Delegates the extraction of a project's files and directories by file traits.

    A file's traits are identified first, and the file is read by the
    extractor registered for its language. A directory is described by the
    factory registered for the language that most of the files beneath it are
    written in. A file or directory with nothing registered for its language
    is handled in a language-neutral way.
    """

    def __init__(
        self,
        file_traits_identifier: BaseFileTraitsIdentifier,
        language_to_file_metadata_extractor: Mapping[str, BaseFileMetadataExtractor],
        language_to_directory_unit_factory: Mapping[str, BaseDirectoryUnitFactory],
    ) -> None:
        self._file_traits_identifier = file_traits_identifier
        self._language_to_file_metadata_extractor = {
            language.lower(): extractor
            for language, extractor in language_to_file_metadata_extractor.items()
        }
        self._language_to_directory_unit_factory = {
            language.lower(): factory
            for language, factory in language_to_directory_unit_factory.items()
        }
        self._language_neutral_extractor = LanguageNeutralFileMetadataExtractor()
        self._language_neutral_factory = LanguageNeutralDirectoryUnitFactory()

    def delegate_file_extraction(self, path: Path) -> AuditableFileMetadataUnit:
        """Identify the file's traits and have the matching extractor read it."""
        traits = self._file_traits_identifier.identify(path)
        extractor: BaseFileMetadataExtractor = self._language_neutral_extractor
        if traits.language is not None:
            extractor = self._language_to_file_metadata_extractor.get(
                traits.language.lower(), extractor
            )
        return extractor.extract_file(path, traits)

    def delegate_directory_building(
        self,
        directory_path: Path,
        files: list[AuditableFileMetadataUnit],
        subdirectories: list[AuditableDirectoryUnit],
    ) -> AuditableDirectoryUnit:
        """Have the matching factory describe a directory whose contents are built."""
        language = self._identify_most_used_language(files, subdirectories)
        factory: BaseDirectoryUnitFactory = self._language_neutral_factory
        if language is not None:
            factory = self._language_to_directory_unit_factory[language]
        return factory.build(directory_path, files, subdirectories, language)

    def update_units_after_full_walk(
        self, root_unit: AuditableDirectoryUnit
    ) -> AuditableDirectoryUnit:
        """Let every registered factory make the changes that had to wait."""
        for language in sorted(self._language_to_directory_unit_factory):
            factory = self._language_to_directory_unit_factory[language]
            root_unit = factory.update_units_after_full_walk(root_unit)
        return root_unit

    def _identify_most_used_language(
        self,
        files: Sequence[AuditableFileMetadataUnit],
        subdirectories: Sequence[AuditableDirectoryUnit],
    ) -> str | None:
        """Return the language with a factory that most files beneath are written in.

        A tie goes to the name that sorts first. None means no file beneath
        is in a language with a factory.
        """
        language_to_file_count = Counter(
            language
            for language in _collect_languages_beneath(files, subdirectories)
            if language in self._language_to_directory_unit_factory
        )
        if not language_to_file_count:
            return None
        return min(
            language_to_file_count,
            key=lambda language: (-language_to_file_count[language], language),
        )


def _collect_languages_beneath(
    files: Sequence[AuditableFileMetadataUnit],
    subdirectories: Sequence[AuditableDirectoryUnit],
) -> Iterator[str]:
    """Yield the language of every file in a directory's tree that has one."""
    for file_unit in files:
        if file_unit.language is not None:
            yield file_unit.language.lower()
    for subdirectory in subdirectories:
        yield from _collect_languages_beneath(
            subdirectory.files, subdirectory.subdirectories
        )
