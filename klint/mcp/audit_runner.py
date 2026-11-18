"""Runs one audit for a tool call and shapes its result as --json would."""

import asyncio
from dataclasses import dataclass
from pathlib import Path

from mcp.server.mcpserver.exceptions import ToolError

from klint.app import AppSettings, BindingOverride, JudgeMode
from klint.app.audit_json import convert_audit_outcome_to_dict
from klint.app.pipeline import AuditOutcome, AuditPipeline, AuditRequest
from klint.app.staged_change import StagedChangeScope, read_staged_change_scope
from klint.catalog.domain_neutral.git import DiffUnits
from klint.composition import create_built_in_injector
from klint.core.models.audits import AuditInput, DiskPathInput
from klint.infra.rule_loader import JsonFileRuleSource
from klint.mcp.audit_tool import AuditTool
from klint.mcp.progress import BaseProgressReporter, ProgressNotifyingListener
from klint.mcp.working_directory import resolve_path_inside


@dataclass(frozen=True)
class AuditToolArguments:
    """What one call of an audit tool asks for.

    path is the path to audit, inside the working directory; None with
    diff_units, when the staged change of the working directory's
    repository is audited instead. rules_path is a file of custom rules.
    should_show_all_answers asks for every answer, not the problems only,
    and min_confidence is the least confidence a finding needs.
    """

    path: str | None
    diff_units: DiffUnits | None = None
    rules_path: str | None = None
    should_show_all_answers: bool = False
    min_confidence: float = 0.0


class AuditToolRunner:
    """Runs the audits the tools ask for, in the server's working directory.

    Each call loads the settings as the commands do, from the environment
    and the project's klint.json, and audits with the built-in suites.
    binding_overrides replace bindings, as for a test's judge.
    """

    def __init__(
        self, working_directory: Path, *binding_overrides: BindingOverride
    ) -> None:
        self._working_directory = working_directory
        self._binding_overrides = binding_overrides

    async def run_audit(
        self,
        tool: AuditTool,
        arguments: AuditToolArguments,
        progress_reporter: BaseProgressReporter,
    ) -> dict[str, object]:
        """Audit what ``arguments`` name with ``tool``; return the JSON report.

        Raises ToolError, with the reason, when the audit cannot run, when
        no unit could be audited, as when the judge is down, or when the
        judge would be run in this process.
        """
        target = (
            None
            if arguments.path is None
            else resolve_path_inside(self._working_directory, arguments.path)
        )
        rules_path = (
            None
            if arguments.rules_path is None
            else resolve_path_inside(self._working_directory, arguments.rules_path)
        )
        try:
            settings = await asyncio.to_thread(
                AppSettings.from_env, target or self._working_directory, rules_path
            )
            _check_judge_is_served(settings)
            audit_pipeline = create_built_in_injector(
                settings, *self._binding_overrides
            ).get(AuditPipeline)
            staged, audit_input = await self._read_audit_input(target, arguments)
            unit_selector = None if staged is None else staged.scope.unit_selector
            listener = ProgressNotifyingListener(progress_reporter)
            outcome = await audit_pipeline.run_audit(
                AuditRequest(
                    audit_input=audit_input,
                    audit_kind_id=tool.audit_kind_id,
                    custom_rule_source=(
                        None
                        if rules_path is None
                        else JsonFileRuleSource(rules_path.resolve(), is_required=True)
                    ),
                    min_confidence=arguments.min_confidence,
                    unit_selector=unit_selector,
                    audit_progress_listener=listener,
                )
            )
        except (OSError, ValueError) as error:
            raise ToolError(str(error)) from error
        await listener.wait_for_notifications()
        _check_some_unit_was_audited(outcome, listener)
        findings = outcome.report.select_findings(
            should_include_non_problems=arguments.should_show_all_answers,
            min_confidence=arguments.min_confidence,
        )
        return convert_audit_outcome_to_dict(outcome, findings, staged)

    async def _read_audit_input(
        self, target: Path | None, arguments: AuditToolArguments
    ) -> tuple[StagedChangeScope | None, AuditInput]:
        """Return the staged change and its input, or the input of the target."""
        if arguments.diff_units is not None:
            staged = await read_staged_change_scope(
                arguments.diff_units, self._working_directory
            )
            return staged, staged.scope.audit_input
        if target is None:
            raise ValueError("A path to audit, or diff, is required")
        return None, DiskPathInput(path=target)


def _check_judge_is_served(settings: AppSettings) -> None:
    """Raise ToolError when the settings would run the model in this process.

    The server expects a judge that is already running and never starts
    one; the local mode would load the model for every call.
    """
    if settings.judge_mode is JudgeMode.LOCAL:
        raise ToolError(
            "klint-mcp asks a judge that is already running, and the settings "
            "choose the local mode, which loads the model in this process. Serve "
            "the judge with kev.serve, or point at Jev, and set "
            "KLINT_JUDGE_MODE=remote in the environment or in the project's "
            "klint.json"
        )


def _check_some_unit_was_audited(
    outcome: AuditOutcome, listener: ProgressNotifyingListener
) -> None:
    """Raise ToolError when units were to be audited and every one failed."""
    selected_unit_count = len(outcome.selected_unit_ids)
    if not selected_unit_count or outcome.report.list_audited_unit_ids():
        return
    first_failure = listener.unit_failures[0]
    raise ToolError(
        f"None of the {selected_unit_count} unit(s) to audit could be audited; "
        f"the judge could not answer about '{first_failure.unit_id}': "
        f"{first_failure.error}"
    )
