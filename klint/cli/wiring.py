"""Builds the injector the commands run with.

The commands audit with the built-in suites, and each command's rule
replacement setting is the one for its kind of audit.
"""

from collections.abc import Mapping
from pathlib import Path

from injector import Injector

from klint.app.settings import AppSettings
from klint.app.wiring import BindingOverride, create_injector
from klint.catalog import BuiltInSuitesModule
from klint.catalog.code import FILE_CONTENTS_KIND_ID, PROJECT_STRUCTURE_KIND_ID


def create_command_injector(
    settings: AppSettings, *binding_overrides: BindingOverride
) -> Injector:
    """Return the injector of a command for ``settings``.

    Binding overrides add or replace bindings, as for create_injector.
    """
    return create_injector(
        settings,
        BuiltInSuitesModule(),
        *binding_overrides,
        kind_id_to_rule_replacement=_map_kind_id_to_rule_replacement(settings),
    )


def _map_kind_id_to_rule_replacement(settings: AppSettings) -> Mapping[str, Path]:
    """Return the rule replacement each command's kind of audit is set to."""
    kind_id_to_rule_replacement = {
        FILE_CONTENTS_KIND_ID: settings.file_rule_replacement,
        PROJECT_STRUCTURE_KIND_ID: settings.project_rule_replacement,
    }
    return {
        kind_id: rule_replacement
        for kind_id, rule_replacement in kind_id_to_rule_replacement.items()
        if rule_replacement is not None
    }
