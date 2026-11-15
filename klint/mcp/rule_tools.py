"""The tools about rules: what a path would be asked, and what one rule says."""

import asyncio
from pathlib import Path

from mcp.server.mcpserver.exceptions import ToolError

from klint.app import AppSettings, BindingOverride
from klint.app.rule_lookup import AskedRule, RuleDefinition, RuleLookup
from klint.composition import create_built_in_injector
from klint.core.models.audits import DiskPathInput
from klint.infra.rule_loader import JsonFileRuleSource
from klint.mcp.audit_tool import FILE_AUDIT_TOOL, STRUCTURE_AUDIT_TOOL, AuditTool
from klint.mcp.working_directory import resolve_path_inside

# The tools in the order their rules are listed; a directory is asked the
# rules of both code audits, a file those of the file audit alone.
_CODE_AUDIT_TOOLS = (FILE_AUDIT_TOOL, STRUCTURE_AUDIT_TOOL)


class RuleToolRunner:
    """Answers the rule tools from the settings of the server's working directory."""

    def __init__(
        self, working_directory: Path, *binding_overrides: BindingOverride
    ) -> None:
        self._working_directory = working_directory
        self._binding_overrides = binding_overrides

    async def list_rules(
        self, path: str, rules_path: str | None = None
    ) -> dict[str, object]:
        """Return the rules an audit of ``path`` would ask, and the exclusions applied.

        A directory is asked the rules of both code audits, a file those of
        the file audit alone.
        """
        target = resolve_path_inside(self._working_directory, path)
        custom_rules_path = (
            None
            if rules_path is None
            else resolve_path_inside(self._working_directory, rules_path)
        )
        tools = _CODE_AUDIT_TOOLS if target.is_dir() else (FILE_AUDIT_TOOL,)
        try:
            lookup = await self._create_rule_lookup(target, custom_rules_path)
            asked_by_tool = [
                (
                    tool,
                    await lookup.list_asked_rules(
                        DiskPathInput(target),
                        tool.audit_kind_id,
                        None
                        if custom_rules_path is None
                        else JsonFileRuleSource(
                            custom_rules_path.resolve(), is_required=True
                        ),
                    ),
                )
                for tool in tools
            ]
        except (OSError, ValueError) as error:
            raise ToolError(str(error)) from error
        return {
            "path": str(target),
            "rules": [
                _convert_asked_rule_to_dict(tool, asked_rule)
                for tool, asked in asked_by_tool
                for asked_rule in asked.rules
            ],
            "applied_rule_exclusions": [
                applied.convert_to_dict()
                for _, asked in asked_by_tool
                for applied in asked.applied_rule_exclusions
            ],
        }

    async def explain_rule(self, rule_id: str) -> dict[str, object]:
        """Return each definition of ``rule_id``: question, unit types, scope, pack."""
        try:
            lookup = await self._create_rule_lookup(self._working_directory, None)
            definitions = lookup.find_rule_definitions(rule_id)
        except (OSError, ValueError) as error:
            raise ToolError(str(error)) from error
        if not definitions:
            raise ToolError(
                f"No rule '{rule_id}' in the packs of the working directory's "
                "settings; list_rules names the rules a path is asked"
            )
        return {
            "rule_id": rule_id,
            "definitions": [
                _convert_definition_to_dict(definition) for definition in definitions
            ],
        }

    async def _create_rule_lookup(
        self, target: Path, custom_rules_path: Path | None
    ) -> RuleLookup:
        settings = await asyncio.to_thread(
            AppSettings.from_env, target, custom_rules_path
        )
        return create_built_in_injector(settings, *self._binding_overrides).get(
            RuleLookup
        )


def _convert_asked_rule_to_dict(tool: AuditTool, asked: AskedRule) -> dict[str, object]:
    return {
        "tool": tool.name,
        "rule_id": asked.rule.rule_id,
        "question": asked.rule.question,
        "unit_types": list(asked.rule.unit_types),
        "tags": list(asked.rule.tags),
        "unit_ids": list(asked.unit_ids),
    }


def _convert_definition_to_dict(definition: RuleDefinition) -> dict[str, object]:
    pack, rule = definition.pack, definition.rule
    return {
        "pack": pack.origin,
        "pack_languages": None
        if pack.scope.languages is None
        else list(pack.scope.languages),
        "question": rule.question,
        "question_with_layers": rule.question_with_layers,
        "unit_type_to_question": dict(rule.unit_type_to_question),
        "unit_types": list(rule.unit_types),
        "languages": list(rule.languages),
        "unit_tags": list(rule.unit_tags),
        "excluded_unit_tags": list(rule.excluded_unit_tags),
        "tags": list(rule.tags),
    }
