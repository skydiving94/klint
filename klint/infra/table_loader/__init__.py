"""The tables read from JSON: the file extensions of each language, and tags."""

from klint.infra.table_loader.language_table_loader import (
    load_file_extension_to_language,
)
from klint.infra.table_loader.tag_table_loader import load_tag_detection_table

__all__ = ["load_file_extension_to_language", "load_tag_detection_table"]
