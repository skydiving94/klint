"""A klint.json turns a rule off for one class or function, by a unit selector."""

import json
from pathlib import Path

import pytest

from klint.core import KlintWarning
from tests.support.builders import DIR_RULE, FILE_RULE, write_text
from tests.support.rule_exclusions import REASON, audit_project, build_exclusion

Capture = pytest.CaptureFixture[str]

RULES = {
    "tidy_file": FILE_RULE,
    "focused": {**FILE_RULE, "unit_types": ["class"]},
    "short": {**FILE_RULE, "question": "Is it short?", "unit_types": ["function"]},
}
SHOP = """class Cart:
    def total(self) -> int:
        return 1


class Till:
    def open(self) -> None:
        return None


def ring() -> int:
    return 2
"""
SETTINGS = """class AppSettings:
    def load(self) -> int:
        return 3


class Other:
    pass
"""


def _list_excluded_units(
    project: Path, capsys: Capture, rule_exclusions: list[object]
) -> dict[str, list[str]]:
    """Audit ``project`` and return each excluded rule's units, from the project."""
    audit_project(project, RULES, rule_exclusions, "--json")
    report = json.loads(capsys.readouterr().out)
    return {
        applied["rule_id"]: [
            unit_id.removeprefix(f"{project}/") for unit_id in applied["unit_ids"]
        ]
        for applied in report.get("applied_rule_exclusions", [])
    }


def _exclude_every_rule(*paths: str) -> list[object]:
    return [build_exclusion(rule_id, *paths) for rule_id in RULES]


@pytest.mark.usefixtures("shell_env")
def test_a_class_selector_covers_its_methods_but_not_the_file(
    tmp_path: Path, capsys: Capture
) -> None:
    project = tmp_path / "project"
    write_text(project / "shop.py", SHOP)

    excluded = _list_excluded_units(
        project, capsys, _exclude_every_rule("shop.py::Cart")
    )

    assert excluded == {
        "focused": ["shop.py::Cart"],
        "short": ["shop.py::Cart.total"],
    }


@pytest.mark.usefixtures("shell_env")
def test_an_excluded_unit_is_not_asked_its_rule(tmp_path: Path) -> None:
    project = tmp_path / "project"
    write_text(project / "shop.py", SHOP)

    subject_to_rule_ids = audit_project(
        project, RULES, [build_exclusion("short", "shop.py::Cart")], "--json"
    )

    asked_short = {
        subject
        for subject, rule_ids in subject_to_rule_ids.items()
        if "short" in rule_ids
    }
    assert asked_short == {
        "def open(self) -> None:\n    return None",
        "def ring() -> int:\n    return 2",
    }


@pytest.mark.usefixtures("shell_env")
def test_a_function_selector_covers_that_function_only(
    tmp_path: Path, capsys: Capture
) -> None:
    project = tmp_path / "project"
    write_text(project / "shop.py", SHOP)

    excluded = _list_excluded_units(
        project, capsys, _exclude_every_rule("shop.py::Cart.total", "shop.py::ring")
    )

    assert excluded == {"short": ["shop.py::Cart.total", "shop.py::ring"]}


@pytest.mark.usefixtures("shell_env")
def test_globs_work_in_the_path_and_in_the_name(
    tmp_path: Path, capsys: Capture
) -> None:
    project = tmp_path / "project"
    write_text(project / "app" / "settings.py", SETTINGS)
    write_text(project / "app" / "nested" / "settings.py", SETTINGS)

    excluded = _list_excluded_units(
        project, capsys, _exclude_every_rule("app/*.py::*Settings")
    )

    assert excluded == {
        "focused": ["app/settings.py::AppSettings"],
        "short": ["app/settings.py::AppSettings.load"],
    }


@pytest.mark.usefixtures("shell_env")
def test_a_star_in_the_name_stops_at_a_dot(tmp_path: Path, capsys: Capture) -> None:
    project = tmp_path / "project"
    write_text(project / "shop.py", SHOP)

    excluded = _list_excluded_units(
        project, capsys, _exclude_every_rule("shop.py::*.open", "shop.py::r*")
    )

    assert excluded == {"short": ["shop.py::Till.open", "shop.py::ring"]}


@pytest.mark.usefixtures("shell_env")
def test_a_stale_selector_warns_once_in_a_full_audit(
    tmp_path: Path, capsys: Capture
) -> None:
    project = tmp_path / "project"
    write_text(project / "shop.py", SHOP)

    audit_project(
        project,
        RULES,
        [
            build_exclusion("short", "shop.py::Cart.total", "shop.py::Basket"),
            build_exclusion("focused", "shop.py::ring"),
        ],
    )

    assert _list_warnings(capsys) == [
        "The rule exclusion of 'short' on shop.py::Basket matched no unit it would "
        "have been asked about: it may be stale, such as for a renamed class or "
        "function",
        "The rule exclusion of 'focused' on shop.py::ring matched no unit it would "
        "have been asked about: it may be stale, such as for a renamed class or "
        "function",
    ]


@pytest.mark.usefixtures("shell_env")
def test_a_selector_outside_the_audited_folder_does_not_warn(
    tmp_path: Path, capsys: Capture
) -> None:
    project = tmp_path / "project"
    write_text(project / "shop" / "cart.py", SHOP)
    write_text(project / "tools" / "till.py", SHOP)

    audit_project(
        project,
        RULES,
        [build_exclusion("short", "tools/till.py::Basket")],
        target=project / "shop",
    )

    assert _list_warnings(capsys) == []


@pytest.mark.usefixtures("shell_env")
def test_an_exclusion_of_a_rule_no_unit_is_asked_does_not_warn(
    tmp_path: Path, capsys: Capture
) -> None:
    project = tmp_path / "project"
    write_text(project / "shop.py", SHOP)

    audit_project(
        project,
        {**RULES, "package_rule": DIR_RULE},
        [build_exclusion("package_rule", "shop")],
    )

    assert _list_warnings(capsys) == []


@pytest.mark.usefixtures("shell_env")
def test_a_selector_for_a_file_klint_does_not_cut_into_units_warns(
    tmp_path: Path, capsys: Capture
) -> None:
    project = tmp_path / "project"
    write_text(project / "notes.md", "# Notes\n")

    audit_project(project, RULES, [build_exclusion("tidy_file", "notes.md::Intro")])

    [warning] = _list_warnings(capsys)
    assert warning.startswith("The rule exclusion of 'tidy_file' on notes.md::Intro")


def _list_warnings(capsys: Capture) -> list[str]:
    """Return the warnings the command printed on stderr."""
    prefix = "[klint] Warning: "
    return [
        line.removeprefix(prefix)
        for line in capsys.readouterr().err.splitlines()
        if line.startswith(prefix)
    ]


@pytest.mark.usefixtures("shell_env")
@pytest.mark.parametrize("entry", ["shop.py::", "::Cart"])
def test_a_selector_missing_a_part_is_left_out_with_a_warning(
    tmp_path: Path, capsys: Capture, entry: str
) -> None:
    project = tmp_path / "project"
    write_text(project / "shop.py", SHOP)

    with pytest.warns(KlintWarning, match="must name a path before '::'"):
        excluded = _list_excluded_units(
            project, capsys, [build_exclusion("short", entry)]
        )

    assert excluded == {}


@pytest.mark.usefixtures("shell_env")
def test_the_terminal_report_lists_the_units_a_selector_covered(
    tmp_path: Path, capsys: Capture
) -> None:
    project = tmp_path / "project"
    write_text(project / "shop.py", SHOP)

    audit_project(project, RULES, [build_exclusion("short", "shop.py::Cart")])

    out = capsys.readouterr().out
    assert f"short\x1b[0m on shop.py::Cart (1 unit(s)): {REASON}\n" in out
    assert f"\n      {project / 'shop.py'}::Cart.total\n" in out
