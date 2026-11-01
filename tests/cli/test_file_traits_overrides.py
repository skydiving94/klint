"""A project's klint.json binding_overrides the language and tags detected for files."""

import asyncio
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest

from klint.app.settings import AppSettings
from klint.cli.file_audit import FILE_AUDIT_COMMAND
from klint.core.klint_warning import KlintWarning
from tests.support.builders import (
    FILE_RULE,
    build_audit_command_app,
    write_json,
    write_text,
)
from tests.support.fakes import FakeJudge

TAGGED_RULES = {
    "backend_rule": {**FILE_RULE, "unit_tags": ["backend"]},
    "frontend_rule": {**FILE_RULE, "unit_tags": ["frontend"]},
    "python_rule": {**FILE_RULE, "languages": ["python"]},
}


def _audit_project(
    project: Path, file_traits: list[dict[str, Any]]
) -> dict[str, set[str]]:
    """Run klint on ``project``, whose klint.json holds ``file_traits``.

    The only rules are those of its klint.json. Return the rule IDs asked
    about each file, by the file's content.
    """
    write_json(
        project / "klint.json", {"file_traits": file_traits, "rules": TAGGED_RULES}
    )
    settings = replace(
        AppSettings.from_env(project), built_in_rule_packs=(), fallback_rule_packs=()
    )
    judge = FakeJudge()
    app = build_audit_command_app(FILE_AUDIT_COMMAND, judge, settings)
    asyncio.run(app.run([str(project), "--json"]))
    return judge.subject_to_asked_rule_ids()


@pytest.mark.usefixtures("shell_env")
def test_override_tags_win_over_every_detected_tag(tmp_path: Path) -> None:
    project = tmp_path / "project"
    # Backend by its folder and by its import.
    write_text(project / "api" / "views.py", "import sqlalchemy\n")

    content_to_rule_ids = _audit_project(
        project, [{"glob": "api/**", "tags": ["frontend"]}]
    )

    assert content_to_rule_ids == {
        "import sqlalchemy\n": {"frontend_rule", "python_rule"}
    }


@pytest.mark.usefixtures("shell_env")
def test_first_matching_entry_decides(tmp_path: Path) -> None:
    project = tmp_path / "project"
    write_text(project / "lib" / "db.py", "db = 1\n")
    write_text(project / "lib" / "util.py", "util = 1\n")

    content_to_rule_ids = _audit_project(
        project,
        [
            {"glob": "lib/db.py", "tags": ["backend"]},
            {"glob": "lib/**", "tags": ["frontend"]},
        ],
    )

    assert content_to_rule_ids == {
        "db = 1\n": {"backend_rule", "python_rule"},
        "util = 1\n": {"frontend_rule", "python_rule"},
    }


@pytest.mark.usefixtures("shell_env")
def test_override_language_keeps_the_detected_tags(tmp_path: Path) -> None:
    project = tmp_path / "project"
    write_text(project / "api" / "job.txt", "job = 1\n")

    content_to_rule_ids = _audit_project(
        project, [{"glob": "**/*.txt", "language": "Python"}]
    )

    # Read as Python, and still backend by its folder.
    assert content_to_rule_ids == {"job = 1\n": {"backend_rule", "python_rule"}}


@pytest.mark.usefixtures("shell_env")
def test_glob_matches_from_the_folder_of_the_klint_json(tmp_path: Path) -> None:
    project = tmp_path / "project"
    write_text(project / "src" / "api" / "views.py", "views = 1\n")

    # The audit target is a subfolder; the glob still starts at the project.
    write_json(
        project / "klint.json",
        {
            "file_traits": [{"glob": "src/api/**", "tags": ["frontend"]}],
            "rules": TAGGED_RULES,
        },
    )
    target = project / "src"
    settings = replace(
        AppSettings.from_env(project), built_in_rule_packs=(), fallback_rule_packs=()
    )
    judge = FakeJudge()
    asyncio.run(
        build_audit_command_app(FILE_AUDIT_COMMAND, judge, settings).run(
            [str(target), "--json"]
        )
    )

    assert judge.subject_to_asked_rule_ids() == {
        "views = 1\n": {"frontend_rule", "python_rule"}
    }


@pytest.mark.usefixtures("shell_env")
@pytest.mark.parametrize(
    ("file_traits", "message"),
    [
        ({"glob": "a/**"}, "is ignored: it must be a list"),
        (["a/**"], "Entry 0 of 'file_traits' .* must be an object"),
        ([{"tags": ["backend"]}], "its 'glob' must be a non-empty string"),
        ([{"glob": "a/**", "tags": "backend"}], "its 'tags' must be a list"),
        ([{"glob": "a/**", "language": 3}], "its 'language' must be"),
        ([{"glob": "a/**"}], "sets neither 'language' nor 'tags'"),
        ([{"glob": "a/**", "tag": ["x"], "tags": ["x"]}], r"unknown fields \['tag'\]"),
    ],
)
def test_entry_that_cannot_be_used_is_reported(
    tmp_path: Path, file_traits: object, message: str
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    write_json(project / "klint.json", {"file_traits": file_traits})

    with pytest.warns(KlintWarning, match=message):
        settings = AppSettings.from_env(project)

    # A klint.json with file_traits alone holds no rules.
    assert settings.project_rule_packs == ()


@pytest.mark.usefixtures("shell_env")
def test_override_naming_an_unknown_language_is_warned_about(tmp_path: Path) -> None:
    project = tmp_path / "project"
    write_text(project / "jobs" / "batch.cbl", "DISPLAY 'HI'.\n")

    with pytest.warns(KlintWarning, match="names unknown language 'cobol'"):
        content_to_rule_ids = _audit_project(
            project, [{"glob": "jobs/**", "language": "cobol"}]
        )

    assert content_to_rule_ids == {"DISPLAY 'HI'.\n": {"backend_rule", "frontend_rule"}}
