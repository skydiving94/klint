"""A project's layers, listed in its klint.json, as klint-structure asks about them."""

import asyncio
import json
from pathlib import Path
from typing import Any

import pytest

from klint.app import AppSettings
from klint.cli import STRUCTURE_AUDIT_COMMAND
from klint.core import KlintWarning
from tests.support.builders import (
    build_audit_command_app,
    list_lines_before_judge_usage,
    write_json,
    write_text,
)
from tests.support.fakes import FakeJudge
from tests.support.paths import PYTHON_PACKAGE_RULE_PACK

LAYER_RULE_IDS = ("layering_violation", "leaky_abstraction")


def _read_built_in_rule(rule_id: str) -> dict[str, Any]:
    pack: dict[str, Any] = json.loads(
        PYTHON_PACKAGE_RULE_PACK.read_text(encoding="utf-8")
    )
    rule: dict[str, Any] = pack["rules"][rule_id]
    return rule


def _write_project(project: Path, config: dict[str, Any] | None) -> Path:
    """Write a small Python project, with ``config`` as its klint.json if given."""
    write_text(project / "app" / "__init__.py", "")
    write_text(project / "app" / "core" / "orders.py", "import requests\n")
    write_text(project / "app" / "cli" / "main.py", "from app.core import orders\n")
    if config is not None:
        write_json(project / "klint.json", config)
    return project


def _map_rule_id_to_question(project: Path) -> dict[str, str]:
    """Run klint-structure on ``project`` as the shell would, with a fake judge.

    Return the question asked for each rule about the project's directory.
    """
    judge = FakeJudge()
    settings = AppSettings.from_env(project)
    asyncio.run(
        build_audit_command_app(STRUCTURE_AUDIT_COMMAND, judge, settings).run(
            [str(project)]
        )
    )
    (request,) = [
        request
        for request in judge.requests
        if request.subject.startswith(f"Target Directory Under Audit: {project} ")
    ]
    return {question.question_id: question.question for question in request.questions}


@pytest.mark.usefixtures("shell_env")
def test_layers_in_klint_json_are_shown_for_the_two_layer_rules(
    tmp_path: Path,
) -> None:
    project = _write_project(
        tmp_path / "project", {"layers": ["app.cli", "app.services", "app.core"]}
    )

    rule_id_to_question = _map_rule_id_to_question(project)

    for rule_id in LAYER_RULE_IDS:
        assert rule_id_to_question[rule_id] == _read_built_in_rule(rule_id)[
            "question_with_layers"
        ].replace("{layers}", "app.cli, app.services, app.core")
    # Every other rule is asked as it is without layers.
    assert (
        rule_id_to_question["flat_structure"]
        == (_read_built_in_rule("flat_structure")["question"])
    )


@pytest.mark.usefixtures("shell_env")
def test_without_layers_the_two_layer_rules_are_asked_as_before(
    tmp_path: Path,
) -> None:
    project = _write_project(tmp_path / "project", None)

    rule_id_to_question = _map_rule_id_to_question(project)

    for rule_id in LAYER_RULE_IDS:
        assert rule_id_to_question[rule_id] == _read_built_in_rule(rule_id)["question"]


@pytest.mark.usefixtures("shell_env")
def test_layers_that_are_not_a_list_of_names_are_ignored_with_a_warning(
    tmp_path: Path,
) -> None:
    project = _write_project(tmp_path / "project", {"layers": "app.cli > app.core"})

    with pytest.warns(KlintWarning, match="'layers' key .* is ignored"):
        rule_id_to_question = _map_rule_id_to_question(project)

    assert (
        rule_id_to_question["layering_violation"]
        == (_read_built_in_rule("layering_violation")["question"])
    )


@pytest.mark.usefixtures("shell_env")
def test_a_rule_can_ask_its_own_question_with_the_layers(tmp_path: Path) -> None:
    house_rule = {
        "type": "choice",
        "question": "Is the code layered?",
        "question_with_layers": "Do imports respect the layers {layers}?",
        "unit_types": ["project_directory"],
    }
    project = _write_project(
        tmp_path / "project",
        {"layers": ["app.cli", "app.core"], "rules": {"layered": house_rule}},
    )

    rule_id_to_question = _map_rule_id_to_question(project)

    assert rule_id_to_question["layered"] == (
        "Do imports respect the layers app.cli, app.core?"
    )


@pytest.mark.usefixtures("shell_env")
def test_a_question_with_layers_that_does_not_show_them_is_warned_about(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    house_rule = {
        "type": "choice",
        "question": "Is the code layered?",
        "question_with_layers": "Do imports respect the layers?",
        "unit_types": ["project_directory"],
    }
    project = _write_project(
        tmp_path / "project",
        {"layers": ["app.cli", "app.core"], "rules": {"layered": house_rule}},
    )

    rule_id_to_question = _map_rule_id_to_question(project)

    assert rule_id_to_question["layered"] == "Do imports respect the layers?"
    assert list_lines_before_judge_usage(capsys.readouterr().err) == [
        f"[klint-structure] Warning: Rule 'layered' in '{project / 'klint.json'}' "
        "has a question_with_layers without {layers}, so it does not show the "
        "project's layers"
    ]
