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


IMPORT_IDENTIFIER = TagDetectingFileTraitsIdentifier(
    ExtensionFileTraitsIdentifier({".py": "python", ".ts": "typescript"}),
    TagDetectionTable(
        path_glob_to_tags={"**/api/**": BACKEND},
        import_to_tags={
            "sqlalchemy": BACKEND,
            "react": FRONTEND,
            "@angular/core": FRONTEND,
            "org.springframework": BACKEND,
        },
    ),
)


@pytest.mark.parametrize(
    "file_start",
    [
        "import os\nimport sqlalchemy\n",
        "import os, sqlalchemy.orm\n",
        "from sqlalchemy.orm import Session\n",
        "def f():\n    from sqlalchemy import select\n",
        "import org.springframework.web.bind.annotation.RestController;\n",
    ],
)
def test_backend_imports_add_the_backend_tag(file_start: str) -> None:
    traits = IMPORT_IDENTIFIER.identify(ROOT / "lib" / "db.py", ROOT)

    assert IMPORT_IDENTIFIER.identify_from_file_start(
        ROOT / "lib" / "db.py", traits, file_start
    ) == UnitTraits(language="python", tags=BACKEND)


@pytest.mark.parametrize(
    "file_start",
    [
        "import React, { useState } from 'react';\n",
        'import { createRoot } from "react/client";\n',
        "const React = require('react');\n",
        "import { Component } from '@angular/core';\n",
        "import '@angular/core/testing';\n",
    ],
)
def test_frontend_imports_add_the_frontend_tag(file_start: str) -> None:
    traits = IMPORT_IDENTIFIER.identify(ROOT / "lib" / "view.ts", ROOT)

    assert (
        IMPORT_IDENTIFIER.identify_from_file_start(
            ROOT / "lib" / "view.ts", traits, file_start
        ).tags
        == FRONTEND
    )


@pytest.mark.parametrize(
    "file_start",
    [
        "from . import sqlalchemy\n",
        "import './react';\n",
        "# We could import sqlalchemy here.\n",
        "import sqlalchemyx\n",
        "import '@angular/corex';\n",
    ],
)
def test_relative_commented_or_other_imports_add_no_tag(file_start: str) -> None:
    traits = IMPORT_IDENTIFIER.identify(ROOT / "lib" / "a.py", ROOT)

    assert (
        IMPORT_IDENTIFIER.identify_from_file_start(
            ROOT / "lib" / "a.py", traits, file_start
        ).tags
        == frozenset()
    )


def test_import_tags_add_to_the_tags_of_the_path() -> None:
    path = ROOT / "api" / "view.ts"
    traits = IMPORT_IDENTIFIER.identify(path, ROOT)

    assert (
        IMPORT_IDENTIFIER.identify_from_file_start(
            path, traits, "import React from 'react';\n"
        ).tags
        == BACKEND | FRONTEND
    )


def test_glob_with_repeated_folder_wildcards_fails_fast_on_a_long_path() -> None:
    identifier = TagDetectingFileTraitsIdentifier(
        ExtensionFileTraitsIdentifier({}),
        TagDetectionTable(path_glob_to_tags={"**/" * 30 + "api/x": BACKEND}),
    )
    deep_path = ROOT.joinpath(*["dir"] * 40, "api", "y")

    assert identifier.identify(deep_path, ROOT).tags == frozenset()
    assert identifier.identify(ROOT / "a" / "api" / "x", ROOT).tags == BACKEND
