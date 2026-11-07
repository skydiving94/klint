"""The names a scan of an audit target leaves out."""

from dataclasses import dataclass


@dataclass(frozen=True)
class IgnoredNames:
    """The names a scan leaves out.

    directory_names and file_names are compared with the name of an entry.
    file_suffixes are compared with the suffix of a file in lower case, with
    its leading dot, such as ".png".
    """

    directory_names: frozenset[str] = frozenset()
    file_names: frozenset[str] = frozenset()
    file_suffixes: frozenset[str] = frozenset()
