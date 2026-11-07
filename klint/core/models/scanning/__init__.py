"""What a scan of an audit target finds, and what tells each file's traits."""

from klint.core.models.scanning.file_traits_override import FileTraitsOverride
from klint.core.models.scanning.ignored_names import IgnoredNames
from klint.core.models.scanning.scanned_tree import (
    ScannedDirectory,
    ScannedFile,
    ScannedTarget,
)
from klint.core.models.scanning.tag_detection_table import TagDetectionTable

__all__ = [
    "FileTraitsOverride",
    "IgnoredNames",
    "ScannedDirectory",
    "ScannedFile",
    "ScannedTarget",
    "TagDetectionTable",
]
