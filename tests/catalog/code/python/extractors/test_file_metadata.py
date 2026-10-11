"""Python file metadata: imports, exports, classes and functions."""

from pathlib import Path

from src.catalog.code.python.extractors.file_metadata import (
    PythonFileMetadataExtractor,
)
from src.core.models.file_traits import FileTraits
from tests.support.builders import write_text

PYTHON = FileTraits(language="python")

MODULE_SOURCE = """\
import os
import json as j
from pathlib import Path
from . import sibling
from .models import order
from pkg.sub import helper_fn, HelperClass

__all__ = ["run", "Public"]


class Public:
    def method(self):
        return None


def run():
    import sqlite3


async def arun():
    return None
"""


def test_python_metadata_lists_imports_exports_classes_and_functions(
    tmp_path: Path,
) -> None:
    target = write_text(tmp_path / "module.py", MODULE_SOURCE)

    unit = PythonFileMetadataExtractor().extract_file(target, PYTHON)

    assert unit.unit_type == "file_metadata"
    assert unit.file_name == "module.py"
    assert unit.line_count == len(MODULE_SOURCE.splitlines())
    # Top-level imports in source order, then the one nested inside run().
    assert unit.imports == [
        "os",
        "json",
        "pathlib",
        ".",
        ".sibling",
        ".models",
        ".models.order",
        "pkg.sub",
        "pkg.sub.helper_fn",
        "sqlite3",
    ]
    assert unit.exports == ["Public", "run"]
    assert unit.classes == ["Public"]
    assert unit.functions == ["run", "arun"]


def test_init_file_exports_the_names_it_imports(tmp_path: Path) -> None:
    source = "from .a import Foo, bar as baz\n"
    init_unit = PythonFileMetadataExtractor().extract_file(
        write_text(tmp_path / "__init__.py", source), PYTHON
    )
    plain_unit = PythonFileMetadataExtractor().extract_file(
        write_text(tmp_path / "plain.py", source), PYTHON
    )
    assert init_unit.exports == ["Foo", "baz"]
    assert plain_unit.exports == []


def test_python_metadata_survives_a_syntax_error(tmp_path: Path) -> None:
    target = write_text(tmp_path / "broken.py", "def (:\n    pass\n")

    unit = PythonFileMetadataExtractor().extract_file(target, PYTHON)

    assert unit.line_count == 2
    assert (unit.imports, unit.exports, unit.classes, unit.functions) == (
        [],
        [],
        [],
        [],
    )
