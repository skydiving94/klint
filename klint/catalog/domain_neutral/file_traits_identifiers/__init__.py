"""What tells a file's traits: its extension, the tags it shows, a project's say."""

from klint.catalog.domain_neutral.file_traits_identifiers.extension_identifier import (
    ExtensionFileTraitsIdentifier,
)
from klint.catalog.domain_neutral.file_traits_identifiers.overriding_identifier import (
    OverridingFileTraitsIdentifier,
)
from klint.catalog.domain_neutral.file_traits_identifiers.tag_detecting_identifier import (  # noqa: E501
    TagDetectingFileTraitsIdentifier,
)

__all__ = [
    "ExtensionFileTraitsIdentifier",
    "OverridingFileTraitsIdentifier",
    "TagDetectingFileTraitsIdentifier",
]
