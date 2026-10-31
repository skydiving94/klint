"""The signals that tell which side of a project a file belongs to."""

from collections.abc import Mapping
from dataclasses import dataclass, field


@dataclass(frozen=True)
class TagDetectionTable:
    """The tags each signal in a file's path stands for.

    extension_to_tags gives the tags of a file extension, with its leading
    dot and in lower case, such as ".tsx". path_glob_to_tags gives the tags
    of a file whose path, from the scanned target down, matches a glob such
    as "**/api/**". Tags are in lower case.
    """

    extension_to_tags: Mapping[str, frozenset[str]] = field(default_factory=dict)
    path_glob_to_tags: Mapping[str, frozenset[str]] = field(default_factory=dict)
