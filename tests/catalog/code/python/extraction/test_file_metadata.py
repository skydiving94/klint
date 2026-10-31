"""Python file metadata: imports, exports, classes and functions."""

from pathlib import Path

import pytest

from klint.catalog.code.python.extraction.file_metadata import (
    PythonFileMetadataExtractor,
)
from klint.core.klint_warning import KlintWarning
from klint.core.models.unit_traits import UnitTraits
from tests.support.builders import write_text

PYTHON = UnitTraits(language="python")

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
    assert not unit.is_unparseable


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


# Each is a way the parser gives up on a file.
@pytest.mark.parametrize(
    "source",
    [
        pytest.param("import json\ndef (:\n    pass\n", id="syntax_error"),
        pytest.param("-" * 200_000 + "1\n", id="parser_stack_overflow"),
        pytest.param("x = " + "1+" * 100_000 + "1\n", id="ast_too_deep"),
    ],
)
def test_python_file_that_cannot_be_parsed_is_marked_with_a_warning(
    tmp_path: Path, source: str
) -> None:
    # Such a file was described as empty, with no warning, so the judge took
    # its empty lists for facts (issue #20). Its lists stay empty, but it is
    # marked, so that they read as unknown.
    target = write_text(tmp_path / "broken.py", source)

    with pytest.warns(KlintWarning, match="it cannot be parsed") as caught:
        unit = PythonFileMetadataExtractor().extract_file(target, PYTHON)

    assert len(caught) == 1
    assert unit.is_unparseable
    assert unit.line_count == len(source.splitlines())
    assert (unit.imports, unit.exports, unit.classes, unit.functions) == (
        [],
        [],
        [],
        [],
    )
