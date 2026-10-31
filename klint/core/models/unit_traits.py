"""What klint can tell about a unit before reading what it holds."""

from dataclasses import dataclass


@dataclass(frozen=True)
class UnitTraits:
    """What is known about a unit from the outside, such as a file's language.

    Rules can be limited to units with some traits. language is the
    language the unit's content is written in, programming or natural (for
    example "python" or "english"); None when unknown or when the content
    has no language, such as an image or a summary.
    """

    language: str | None = None
