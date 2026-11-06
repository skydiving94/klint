"""What klint-structure tells the judge for the built-in structure rules.

Each limit a rule uses is stated in its question, and the judge is shown
the measure it is checked against.
"""

import asyncio
from pathlib import Path

from klint.app import AppSettings
from klint.cli import STRUCTURE_AUDIT_COMMAND
from klint.core.models.judging import JudgeRequest
from tests.support.builders import build_audit_command_app, make_settings, write_text
from tests.support.fakes import FakeJudge
from tests.support.paths import PYTHON_PACKAGE_RULE_PACK


def _audit_with_the_structure_rules(
    target: Path, settings: AppSettings | None = None
) -> FakeJudge:
    """Run klint-structure on ``target`` with the built-in structure rules.

    Return the fake judge, which holds each request it was sent.
    """
    judge = FakeJudge()
    app = build_audit_command_app(
        STRUCTURE_AUDIT_COMMAND,
        judge,
        settings or make_settings(built_in_rule_packs=[PYTHON_PACKAGE_RULE_PACK]),
    )
    asyncio.run(app.run([str(target)]))
    return judge


def _find_request_about(judge: FakeJudge, directory: Path) -> JudgeRequest:
    """Return the one request the judge was sent about ``directory``."""
    (request,) = [
        request
        for request in judge.requests
        if request.subject.startswith(f"Target Directory Under Audit: {directory} ")
    ]
    return request


def _find_question(request: JudgeRequest, rule_id: str) -> str:
    """Return the question ``request`` asks for ``rule_id``."""
    (question,) = [
        question.question
        for question in request.questions
        if question.question_id == rule_id
    ]
    return question


def test_flat_structure_states_its_limit_and_shows_the_module_count(
    tmp_path: Path,
) -> None:
    package = tmp_path / "pkg"
    write_text(package / "__init__.py", "")
    for index in range(16):
        write_text(package / f"module_{index:02}.py", "x = 1\n")
    write_text(package / "notes.md", "# Notes\n")

    judge = _audit_with_the_structure_rules(package)

    request = _find_request_about(judge, package)
    assert "more than 15 modules" in _find_question(request, "flat_structure")
    assert "besides __init__.py" in _find_question(request, "flat_structure")
    # Only the Python modules count: not __init__.py, nor the other files.
    module_names = ", ".join(f"module_{index:02}.py" for index in range(16))
    assert (
        f"Python Modules Directly In It, Besides __init__.py: 16 [{module_names}]"
    ) in request.subject.splitlines()


def test_nesting_depth_counts_from_the_directory_and_shows_the_deepest_level(
    tmp_path: Path,
) -> None:
    package = tmp_path / "pkg"
    write_text(package / "__init__.py", "")
    write_text(package / "shallow" / "a.py", "x = 1\n")
    write_text(package / "data" / "catalog" / "code" / "rules.py", "x = 1\n")

    judge = _audit_with_the_structure_rules(package)

    root_request = _find_request_about(judge, package)
    data_request = _find_request_about(judge, package / "data")
    question = _find_question(root_request, "excessive_nesting_depth")
    assert "3 levels down or fewer" in question
    assert "below this directory" in question
    assert (
        "Deepest Subdirectory Below This Directory: data/catalog/code (3 levels down)"
    ) in root_request.subject.splitlines()
    assert (
        "Deepest Subdirectory Below This Directory: catalog/code (2 levels down)"
    ) in data_request.subject.splitlines()
