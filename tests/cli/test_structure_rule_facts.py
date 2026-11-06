"""What klint-structure tells the judge for the built-in structure rules.

Each limit a rule uses is stated in its question, and the judge is shown
the measure it is checked against.
"""

import asyncio
from pathlib import Path

import pytest

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


def _list_importer_lines(request: JudgeRequest) -> list[str]:
    """Return the lines on what the rest of the tree imports of the package."""
    lines = request.subject.splitlines()
    (start,) = [
        index
        for index, line in enumerate(lines)
        if line.startswith("Imported From Elsewhere in the Audited Tree")
    ]
    return lines[start : start + 4]


def test_each_package_shows_what_the_rest_of_the_tree_imports_of_it(
    tmp_path: Path,
) -> None:
    project = tmp_path / "project"
    write_text(project / "shop" / "__init__.py", "from .cart import Cart\n")
    write_text(project / "shop" / "cart.py", "class Cart:\n    pass\n")
    write_text(project / "shop" / "pricing" / "__init__.py", "")
    write_text(project / "shop" / "pricing" / "rules.py", "def discount(): ...\n")
    write_text(project / "web" / "__init__.py", "")
    write_text(
        project / "web" / "views.py",
        "from shop import Cart\nimport shop.cart\n"
        "from shop.pricing.rules import discount\n",
    )
    write_text(project / "web" / "api.py", "from shop.pricing import rules\n")

    judge = _audit_with_the_structure_rules(project)

    # The package's own imports of its modules are not counted.
    assert _list_importer_lines(_find_request_about(judge, project / "shop")) == [
        "Imported From Elsewhere in the Audited Tree (callers outside the tree, "
        "such as tests, entry points or other projects, are not counted):",
        "  The package itself: by 1 module [web.views]",
        "  Its subpackages: by 1 module, as [shop.pricing]",
        "  Its module files directly: by 2 modules, as [shop.cart, shop.pricing.rules]",
    ]
    assert _list_importer_lines(_find_request_about(judge, project / "web"))[1:] == [
        "  The package itself: none",
        "  Its subpackages: none",
        "  Its module files directly: none",
    ]
    # Every caller of the audited directory itself is outside the tree.
    assert _list_importer_lines(_find_request_about(judge, project))[0] == (
        "Imported From Elsewhere in the Audited Tree: not shown, since this is "
        "the audited directory itself; all its callers, such as tests, entry "
        "points or other projects, are outside the tree"
    )


def test_importers_are_named_from_an_audited_package_and_its_relative_imports(
    tmp_path: Path,
) -> None:
    package = tmp_path / "app"
    write_text(package / "__init__.py", "")
    write_text(package / "store" / "__init__.py", "")
    write_text(package / "store" / "orders.py", "x = 1\n")
    write_text(package / "web" / "__init__.py", "")
    write_text(package / "web" / "routes.py", "from ..store import orders\n")

    judge = _audit_with_the_structure_rules(package)

    assert _list_importer_lines(_find_request_about(judge, package / "store"))[1:] == [
        "  The package itself: by 1 module [app.web.routes]",
        "  Its subpackages: none",
        "  Its module files directly: by 1 module, as [app.store.orders]",
    ]


def test_a_folder_holding_a_package_is_read_as_a_folder_on_the_import_path(
    tmp_path: Path,
) -> None:
    repo = tmp_path / "repo"
    write_text(repo / "src" / "shop" / "__init__.py", "")
    write_text(repo / "src" / "shop" / "cart.py", "x = 1\n")
    write_text(repo / "tests" / "test_cart.py", "from shop.cart import x\n")

    judge = _audit_with_the_structure_rules(repo)

    request = _find_request_about(judge, repo / "src" / "shop")
    assert _list_importer_lines(request)[1:] == [
        "  The package itself: none",
        "  Its subpackages: none",
        "  Its module files directly: by 1 module, as [shop.cart]",
    ]


def test_a_folder_holding_no_module_is_not_asked_the_rules_about_modules(
    tmp_path: Path,
) -> None:
    package = tmp_path / "pkg"
    write_text(package / "__init__.py", "")
    write_text(package / "core" / "orders.py", "x = 1\n")
    write_text(package / "resources" / "__init__.py", "")
    write_text(package / "resources" / "catalog" / "rules.json", "{}\n")

    judge = _audit_with_the_structure_rules(package)

    module_rules = {"dead_code_module", "missing_package_public_api"}
    rule_ids_by_directory = {
        name: {q.question_id for q in _find_request_about(judge, path).questions}
        for name, path in (
            ("resources", package / "resources"),
            ("core", package / "core"),
        )
    }
    assert not module_rules & rule_ids_by_directory["resources"]
    assert "flat_structure" in rule_ids_by_directory["resources"]
    assert module_rules <= rule_ids_by_directory["core"]


@pytest.mark.usefixtures("in_repo_root")
def test_klint_resources_is_not_asked_the_rules_about_modules() -> None:
    judge = _audit_with_the_structure_rules(Path("klint"))

    request = _find_request_about(judge, Path("klint") / "resources")
    rule_ids = {question.question_id for question in request.questions}
    assert "dead_code_module" not in rule_ids
    assert "missing_package_public_api" not in rule_ids
