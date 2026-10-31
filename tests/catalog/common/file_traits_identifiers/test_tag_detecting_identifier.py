"""Tags from a file's extension and path, read from the detection tables."""

from pathlib import Path

import pytest

from klint.catalog.common.file_traits_identifiers.extension_identifier import (
    ExtensionFileTraitsIdentifier,
)
from klint.catalog.common.file_traits_identifiers.tag_detecting_identifier import (
    TagDetectingFileTraitsIdentifier,
)
from klint.core.models.tag_detection_table import TagDetectionTable
from klint.core.models.unit_traits import UnitTraits

BACKEND = frozenset({"backend"})
FRONTEND = frozenset({"frontend"})
IDENTIFIER = TagDetectingFileTraitsIdentifier(
    ExtensionFileTraitsIdentifier({".py": "python", ".tsx": "typescript"}),
    TagDetectionTable(
        extension_to_tags={".tsx": FRONTEND, ".sql": BACKEND},
        path_glob_to_tags={
            "**/api/**": BACKEND,
            "**/*backend*": BACKEND,
            "src/web/*.py": FRONTEND,
        },
    ),
)
ROOT = Path("/repo")


@pytest.mark.parametrize(
    ("path", "tags"),
    [
        ("ui/Button.tsx", FRONTEND),
        ("db/schema.SQL", BACKEND),
        ("api/routes.py", BACKEND),
        ("app/api/v1/routes.py", BACKEND),
        ("services/user_backend.py", BACKEND),
        ("src/web/view.py", FRONTEND),
        ("src/web/deeper/view.py", frozenset()),
        ("lib/util.py", frozenset()),
    ],
)
def test_tags_come_from_the_extension_and_the_path(
    path: str, tags: frozenset[str]
) -> None:
    assert IDENTIFIER.identify(ROOT / path, ROOT).tags == tags


def test_file_showing_frontend_and_backend_signals_has_both_tags() -> None:
    assert IDENTIFIER.identify(ROOT / "api" / "Form.tsx", ROOT) == UnitTraits(
        language="typescript", tags=BACKEND | FRONTEND
    )


def test_folders_above_the_scanned_target_tell_nothing() -> None:
    root = Path("/home/me/api/project")

    assert IDENTIFIER.identify(root / "lib" / "util.py", root).tags == frozenset()
    assert IDENTIFIER.identify(root / "api" / "util.py", root).tags == BACKEND


def test_file_scanned_as_a_target_of_its_own_is_matched_by_its_name() -> None:
    path = Path("/home/me/api/backend_jobs.py")

    assert IDENTIFIER.identify(path, path.parent).tags == BACKEND


def test_language_still_comes_from_the_extension() -> None:
    assert IDENTIFIER.identify(ROOT / "api" / "routes.py", ROOT).language == "python"
