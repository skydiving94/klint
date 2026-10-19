"""Identifying a file's language from its extension."""

from pathlib import Path

import pytest

from klint.catalog.common.file_traits_identifiers.extension_identifier import (
    ExtensionFileTraitsIdentifier,
)
from klint.infra.language_to_file_extensions_loader.json_loader import (
    load_file_extension_to_language,
)
from tests.support.builders import write_json

IDENTIFIER = ExtensionFileTraitsIdentifier({".py": "python", ".tsx": "typescript"})


@pytest.mark.parametrize(
    ("path", "language"),
    [
        ("app.py", "python"),
        ("pkg/sub/App.PY", "python"),
        ("archive.tar.py", "python"),
        (Path("ui/Button.tsx"), "typescript"),
    ],
)
def test_language_comes_from_the_extension(path: str | Path, language: str) -> None:
    assert IDENTIFIER.identify(path).language == language


@pytest.mark.parametrize("path", ["notes.txt", "Makefile", ".gitignore", "bin/deploy"])
def test_unknown_or_missing_extension_gives_no_language(path: str) -> None:
    assert IDENTIFIER.identify(path).language is None


def test_extension_case_is_ignored_on_both_sides() -> None:
    identifier = ExtensionFileTraitsIdentifier({".R": "r"})

    assert identifier.identify("model.r").language == "r"
    assert identifier.identify("model.R").language == "r"


def test_no_known_extensions_identify_nothing() -> None:
    assert ExtensionFileTraitsIdentifier({}).identify("app.py").language is None


def test_identifying_never_opens_the_file(tmp_path: Path) -> None:
    missing = tmp_path / "does_not_exist.py"

    assert IDENTIFIER.identify(missing).language == "python"


def test_language_added_to_the_data_file_is_identified_without_code_change(
    tmp_path: Path,
) -> None:
    path = write_json(tmp_path / "extensions.json", {"kotlin": [".kt", ".kts"]})

    identifier = ExtensionFileTraitsIdentifier(load_file_extension_to_language(path))

    assert identifier.identify("Main.kt").language == "kotlin"
