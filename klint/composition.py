"""Composes the built-in suites with the app: the injector every front end runs.

A command, the Stop hook or an MCP tool audits with the built-in suites, and
the rule replacement setting of each kind of audit is the one its command
takes. Files, classes and functions are cut at the budget of the judge in
use. This sits between the front ends and klint.app, which the suites
contract keeps from importing a named suite.
"""

from collections.abc import Mapping
from pathlib import Path

from injector import Injector

from klint.app import AppSettings, BindingOverride, create_injector
from klint.app.judge_character_budgets import find_judge_character_budget
from klint.catalog import BuiltInSuitesModule
from klint.catalog.code import FILE_CONTENTS_KIND_ID, PROJECT_STRUCTURE_KIND_ID


def create_built_in_injector(
    settings: AppSettings,
    *binding_overrides: BindingOverride,
    code_character_budget: int | None = None,
) -> Injector:
    """Return the injector of a front end for ``settings``.

    Binding overrides add or replace bindings, as for create_injector.
    File, class and function units are cut at ``code_character_budget``
    characters, the budget of the judge the settings choose unless given.
    """
    return create_injector(
        settings,
        BuiltInSuitesModule(),
        *binding_overrides,
        kind_id_to_rule_replacement=_map_kind_id_to_rule_replacement(settings),
        kind_id_to_character_budget={
            FILE_CONTENTS_KIND_ID: (
                find_judge_character_budget(settings.model_name)
                if code_character_budget is None
                else code_character_budget
            )
        },
    )


def _map_kind_id_to_rule_replacement(settings: AppSettings) -> Mapping[str, Path]:
    """Return the rule replacement each kind of audit is set to."""
    kind_id_to_rule_replacement = {
        FILE_CONTENTS_KIND_ID: settings.file_rule_replacement,
        PROJECT_STRUCTURE_KIND_ID: settings.project_rule_replacement,
    }
    return {
        kind_id: rule_replacement
        for kind_id, rule_replacement in kind_id_to_rule_replacement.items()
        if rule_replacement is not None
    }
