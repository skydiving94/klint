import asyncio
from collections import Counter
from collections.abc import Iterator, Sequence

from klint.catalog.code.language_neutral.extraction.directory_factory import (
    BaseDirectoryUnitFactory,
)
from klint.catalog.code.language_neutral.extraction.file_metadata_base import (
    BaseFileMetadataExtractor,
)
from klint.catalog.code.language_neutral.units.directory_unit import (
    AuditableDirectoryUnit,
)
from klint.catalog.code.language_neutral.units.file_metadata_unit import (
    AuditableFileMetadataUnit,
)
from klint.catalog.domain_neutral.extraction.traits_based_extraction_delegator import (
    TraitsBasedExtractionDelegator,
)
from klint.core.klint_warning import leave_out_file_on_failure
from klint.core.models.scanned_tree import ScannedDirectory, ScannedFile
from klint.core.models.unit_traits import UnitTraits


class RecursiveProjectExtractor:
    """Builds one composite directory unit for a scanned tree.

    The unit holds the metadata of the files directly in the scanned
    directory and, recursively, of every subdirectory. A file is read by
    the extractor its traits pick. A directory is described by the factory
    picked for the language that most files beneath it are written in,
    among the languages with a factory of their own. A file that cannot be
    read or processed is left out, with a warning.
    """

    def __init__(
        self,
        file_delegator: TraitsBasedExtractionDelegator[BaseFileMetadataExtractor],
        directory_delegator: TraitsBasedExtractionDelegator[BaseDirectoryUnitFactory],
    ) -> None:
        self._file_delegator = file_delegator
        self._directory_delegator = directory_delegator

    async def extract(
        self, scanned_directory: ScannedDirectory
    ) -> AuditableDirectoryUnit:
        """Return the unit of ``scanned_directory``, holding everything beneath it."""
        return await asyncio.to_thread(self._extract_tree, scanned_directory)

    def _extract_tree(
        self, scanned_directory: ScannedDirectory
    ) -> AuditableDirectoryUnit:
        root_unit = self._build_directory_unit(scanned_directory)
        # Each factory of its own makes the changes that had to wait.
        for language in self._directory_delegator.list_languages():
            factory = self._directory_delegator.select_extractor(
                UnitTraits(language=language)
            )
            root_unit = factory.update_units_after_full_walk(root_unit)
        return root_unit

    def _build_directory_unit(
        self, scanned_directory: ScannedDirectory
    ) -> AuditableDirectoryUnit:
        files: list[AuditableFileMetadataUnit] = []
        for scanned_file in scanned_directory.files:
            with leave_out_file_on_failure(scanned_file.path):
                files.append(self._extract_file(scanned_file))
        subdirectories = [
            self._build_directory_unit(scanned_subdirectory)
            for scanned_subdirectory in scanned_directory.subdirectories
        ]
        language = self._identify_most_used_language(files, subdirectories)
        factory = self._directory_delegator.select_extractor(
            UnitTraits(language=language)
        )
        return factory.build(scanned_directory.path, files, subdirectories, language)

    def _extract_file(self, scanned_file: ScannedFile) -> AuditableFileMetadataUnit:
        """Have the extractor that the file's traits pick read the file."""
        dispatch = self._file_delegator.dispatch_file(scanned_file)
        return dispatch.extractor.extract_file(dispatch.dispatched_file)

    def _identify_most_used_language(
        self,
        files: Sequence[AuditableFileMetadataUnit],
        subdirectories: Sequence[AuditableDirectoryUnit],
    ) -> str | None:
        """Return the language with a factory that most files beneath are written in.

        A tie goes to the name that sorts first. None means no file beneath
        is in a language with a factory of its own.
        """
        languages_with_a_factory = set(self._directory_delegator.list_languages())
        language_to_file_count = Counter(
            language
            for language in _collect_languages_beneath(files, subdirectories)
            if language in languages_with_a_factory
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
