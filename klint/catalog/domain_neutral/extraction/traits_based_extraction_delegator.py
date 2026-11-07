"""The one place that picks, by traits, what extracts a file or a directory."""

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Generic, TypeVar

from klint.catalog.domain_neutral.extraction.dispatched_file import DispatchedFile
from klint.catalog.domain_neutral.extraction.file_start import (
    is_binary_start,
    read_file_start,
)
from klint.core.interfaces.file_traits_identifier import BaseFileTraitsIdentifier
from klint.core.models.scanned_tree import ScannedFile
from klint.core.models.unit_traits import UnitTraits

# What is picked: a file extractor or a directory unit factory, for example.
ExtractorT = TypeVar("ExtractorT")


@dataclass(frozen=True)
class FileDispatch(Generic[ExtractorT]):
    """The extractor picked for a file, and the file as it is handed to it."""

    extractor: ExtractorT
    dispatched_file: DispatchedFile


class TraitsBasedExtractionDelegator(Generic[ExtractorT]):
    """Picks, by the traits of a file or directory, what extracts it.

    A kind of audit gives it the extractor for each language it handles and
    the fallback for any other language, or none; it builds none of them
    itself. Languages are matched whatever their case. The start of a file
    is read here, once: its extractor is told whether the file is binary,
    and file_traits_identifier, when given, tells from the start of a text
    file what its path could not.
    """

    def __init__(
        self,
        language_to_extractor: Mapping[str, ExtractorT],
        fallback_extractor: ExtractorT,
        file_traits_identifier: BaseFileTraitsIdentifier | None = None,
    ) -> None:
        self._language_to_extractor = {
            language.lower(): extractor
            for language, extractor in language_to_extractor.items()
        }
        self._fallback_extractor = fallback_extractor
        self._file_traits_identifier = file_traits_identifier

    def dispatch_file(self, scanned_file: ScannedFile) -> FileDispatch[ExtractorT]:
        """Return the extractor for ``scanned_file``, and the file as it takes it.

        Only the start of the file is read. Raises OSError when it cannot be
        read.
        """
        path = scanned_file.path
        file_start = read_file_start(path)
        is_binary = is_binary_start(file_start)
        traits = scanned_file.traits
        if not is_binary and self._file_traits_identifier is not None:
            traits = self._file_traits_identifier.identify_from_file_start(
                path, traits, file_start.decode("utf-8", errors="replace")
            )
        return FileDispatch(
            extractor=self.select_extractor(traits),
            dispatched_file=DispatchedFile(
                path=path, traits=traits, is_binary=is_binary
            ),
        )

    def select_extractor(self, traits: UnitTraits) -> ExtractorT:
        """Return the extractor for the language in ``traits``, else the fallback."""
        if traits.language is None:
            return self._fallback_extractor
        return self._language_to_extractor.get(
            traits.language.lower(), self._fallback_extractor
        )

    def list_languages(self) -> list[str]:
        """Return the languages with an extractor of their own, sorted, lowercase."""
        return sorted(self._language_to_extractor)
