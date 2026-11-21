"""Where the built-in rule packs and data files sit inside the installed package."""

from collections.abc import Sequence
from importlib import resources
from pathlib import Path

# Built-in rule packs, relative to klint/resources/catalog/ and merged in this
# order. Each pack states in its header the files it loads for. A rule of a
# later pack replaces the rule of the same ID in an earlier one, for the files
# the later pack loads for.
_BUILT_IN_RULE_PACKS = (
    "code/language_neutral/backend.json",
    "code/typescript/react.json",
    "code/language_neutral/file_design.json",
    "code/python/package_structure.json",
    "code/python/functions_and_classes.json",
)
# The packs a file whose language is not identified is asked, unless the
# config file names its own.
_BUILT_IN_FALLBACK_RULE_PACKS = (
    "code/language_neutral/backend.json",
    "code/language_neutral/file_design.json",
)
# The built-in list of languages and their file extensions, relative to
# klint/resources/catalog/.
_BUILT_IN_LANGUAGE_TO_FILE_EXTENSIONS = (
    "code/language_neutral/language_to_file_extensions.json"
)
# The built-in tables that tell which side of a project a file belongs to,
# relative to klint/resources/catalog/.
_BUILT_IN_TAG_DETECTION = "code/language_neutral/tag_detection.json"


def locate_built_in_rule_packs() -> tuple[Path, ...]:
    """Locate the built-in rule packs, in the order they merge."""
    return _locate_built_in_resources(_BUILT_IN_RULE_PACKS)


def locate_built_in_fallback_rule_packs() -> tuple[Path, ...]:
    """Locate the packs a file whose language is not identified is asked."""
    return _locate_built_in_resources(_BUILT_IN_FALLBACK_RULE_PACKS)


def locate_built_in_language_to_file_extensions() -> Path:
    """Locate the built-in list of languages and their file extensions."""
    return _locate_built_in_resource(_BUILT_IN_LANGUAGE_TO_FILE_EXTENSIONS)


def locate_built_in_tag_detection() -> Path:
    """Locate the built-in tag detection tables."""
    return _locate_built_in_resource(_BUILT_IN_TAG_DETECTION)


def _locate_built_in_resource(relative_path: str) -> Path:
    """Locate a built-in data file inside the installed package."""
    catalog = resources.files("klint.resources") / "catalog"
    return Path(str(catalog / relative_path))


def _locate_built_in_resources(relative_paths: Sequence[str]) -> tuple[Path, ...]:
    return tuple(_locate_built_in_resource(relative) for relative in relative_paths)
