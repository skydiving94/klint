"""The files a rule pack is for, as the applies_to header of the pack states them."""

from collections.abc import Sequence
from dataclasses import dataclass


@dataclass(frozen=True)
class PackScope:
    """The files a pack is for, as its header states them.

    languages is None when the pack is not limited to some languages, as for
    a file without a header.
    """

    languages: tuple[str, ...] | None = None

    def matches(self, language: str) -> bool:
        """Return True when the pack is for files written in ``language``."""
        return self.languages is None or language.lower() in self._lowered_languages()

    def narrow(self, rule_languages: Sequence[str]) -> list[str]:
        """Return the languages a rule of this pack is limited to.

        A rule that names no language inherits the pack's; one that does
        keeps those that are also the pack's.
        """
        if self.languages is None:
            return list(rule_languages)
        if not rule_languages:
            return list(self.languages)
        return [
            language
            for language in rule_languages
            if language.lower() in self._lowered_languages()
        ]

    def _lowered_languages(self) -> set[str]:
        return {language.lower() for language in self.languages or ()}
