"""The one place that picks, by traits, what extracts a file or a directory."""

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Generic, TypeVar

from klint.catalog.common.extraction.binary_check import is_likely_binary
from klint.catalog.common.extraction.dispatched_file import DispatchedFile
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
    itself. Languages are matched whatever their case. A file is checked
    here, once, for being binary, and its extractor is told.
    """

    def __init__(
        self,
        language_to_extractor: Mapping[str, ExtractorT],
        fallback_extractor: ExtractorT,
    ) -> None:
        self._language_to_extractor = {
            language.lower(): extractor
            for language, extractor in language_to_extractor.items()
        }
        self._fallback_extractor = fallback_extractor

    def dispatch_file(self, scanned_file: ScannedFile) -> FileDispatch[ExtractorT]:
        """Return the extractor for ``scanned_file``, and the file as it takes it.

        The file is checked for being binary, reading only its start. Raises
        OSError when it cannot be read.
        """
        dispatched_file = DispatchedFile(
            path=scanned_file.path,
            traits=scanned_file.traits,
            is_binary=is_likely_binary(scanned_file.path),
        )
        return FileDispatch(
            extractor=self.select_extractor(scanned_file.traits),
            dispatched_file=dispatched_file,
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
