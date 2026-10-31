"""The one place that picks, by traits, what extracts a file or a directory."""

from collections.abc import Mapping
from typing import Generic, TypeVar

from klint.core.models.unit_traits import UnitTraits

# What is picked: a file extractor or a directory unit factory, for example.
ExtractorT = TypeVar("ExtractorT")


class TraitsBasedExtractionDelegator(Generic[ExtractorT]):
    """Picks, by the traits of a file or directory, what extracts it.

    A kind of audit gives it the extractor for each language it handles and
    the fallback for any other language, or none; it builds none of them
    itself. Languages are matched whatever their case.
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
