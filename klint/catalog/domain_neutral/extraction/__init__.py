"""Extraction that fits any content: by each file's traits, or a whole file as one."""

from klint.catalog.domain_neutral.extraction.dispatched_file import DispatchedFile
from klint.catalog.domain_neutral.extraction.file_start import read_file_start
from klint.catalog.domain_neutral.extraction.traits_based_extraction_delegator import (
    TraitsBasedExtractionDelegator,
)
from klint.catalog.domain_neutral.extraction.whole_file_extractor import (
    WholeFileExtractor,
)

__all__ = [
    "DispatchedFile",
    "TraitsBasedExtractionDelegator",
    "WholeFileExtractor",
    "read_file_start",
]
