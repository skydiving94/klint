"""Builds the injector the commands run with.

The commands audit with the built-in suites, and each command's rule pack
override setting is the one for its kind of audit.
"""

from collections.abc import Mapping
from pathlib import Path

from injector import Injector

from klint.app.settings import AppSettings
from klint.app.wiring import Override, create_injector
from klint.catalog import BuiltInSuitesModule
from klint.catalog.code import FILE_CONTENTS_KIND_ID, PROJECT_STRUCTURE_KIND_ID


def create_command_injector(settings: AppSettings, *overrides: Override) -> Injector:
    """Return the injector of a command for ``settings``.

    Overrides add or replace bindings, as for create_injector.
    """
    return create_injector(
        settings,
        BuiltInSuitesModule(),
        *overrides,
        kind_id_to_rule_pack_override=_map_kind_id_to_rule_pack_override(settings),
    )


def _map_kind_id_to_rule_pack_override(settings: AppSettings) -> Mapping[str, Path]:
    """Return the rule pack override each command's kind of audit is set to."""
    kind_id_to_rule_pack_override = {
        FILE_CONTENTS_KIND_ID: settings.file_contents_rule_pack_override,
        PROJECT_STRUCTURE_KIND_ID: settings.project_structure_rule_pack_override,
    }
    return {
        kind_id: rule_pack_override
        for kind_id, rule_pack_override in kind_id_to_rule_pack_override.items()
        if rule_pack_override is not None
    }
