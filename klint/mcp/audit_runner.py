"""Runs one audit for a tool call and shapes its result as --json would."""

import asyncio
from dataclasses import dataclass
from pathlib import Path

from mcp.server.mcpserver.exceptions import ToolError

from klint.app import AppSettings, BindingOverride, JudgeMode
from klint.app.audit_json import convert_audit_outcome_to_dict
from klint.app.changed_directories import (
    ChangedDirectoriesScope,
    read_changed_directories_scope,
)
from klint.app.diff_change import DiffChangeScope, read_diff_change_scope
from klint.app.pipeline import AuditOutcome, AuditPipeline, AuditRequest
from klint.app.staged_change import StagedChangeScope, read_staged_change_scope
from klint.catalog.code.language_neutral import CODE_IGNORED_NAMES
from klint.catalog.domain_neutral.git import DiffUnits
from klint.composition import create_built_in_injector
from klint.core.interfaces import BaseUnitSelector
from klint.core.models.audits import AuditInput, DiskPathInput
from klint.infra.rule_loader import JsonFileRuleSource
from klint.mcp.audit_tool import AuditTool, DiffScopeKind
from klint.mcp.progress import BaseProgressReporter, ProgressNotifyingListener
from klint.mcp.working_directory import resolve_path_inside

MAX_DIFF_TEXT_BYTES = 2 * 1024 * 1024


@dataclass(frozen=True)
class AuditToolArguments:
    """What one call of an audit tool asks for.

    path is the path to audit, inside the working directory. Without a
    path, diff_text is a unified diff whose change is audited, read against
    the files in the working directory; with neither, diff_units asks for
    the staged change of the working directory's repository. diff_units
    chooses the units of each changed file. rules_path is a file of custom
    rules. should_show_all_answers asks for every answer, not the problems
    only, and min_confidence is the least confidence a finding needs.
    """

    path: str | None
    diff_units: DiffUnits | None = None
    diff_text: str | None = None
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
            chosen = await self._choose_audit_input(tool, target, arguments)
            listener = ProgressNotifyingListener(progress_reporter)
            outcome = await audit_pipeline.run_audit(
                AuditRequest(
                    audit_input=chosen.audit_input,
                    audit_kind_id=tool.audit_kind_id,
                    custom_rule_source=(
                        None
                        if rules_path is None
                        else JsonFileRuleSource(rules_path.resolve(), is_required=True)
                    ),
                    min_confidence=arguments.min_confidence,
                    unit_selector=chosen.unit_selector,
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
        return convert_audit_outcome_to_dict(
            outcome, findings, chosen.staged, chosen.diff_change
        )

    async def _choose_audit_input(
        self, tool: AuditTool, target: Path | None, arguments: AuditToolArguments
    ) -> "_ChosenAuditInput":
        """Return what ``arguments`` ask ``tool`` to audit.

        Raises ValueError when the staged change or the diff cannot be read.
        """
        if arguments.diff_text is not None:
            return await self._choose_diff_change(tool, arguments.diff_text, arguments)
        if target is not None:
            return _ChosenAuditInput(audit_input=DiskPathInput(path=target))
        if arguments.diff_units is None:
            raise ValueError("A path to audit, diff or diff_text is required")
        staged = await read_staged_change_scope(
            arguments.diff_units, self._working_directory
        )
        return _ChosenAuditInput(
            audit_input=staged.scope.audit_input,
            unit_selector=staged.scope.unit_selector,
            staged=staged,
        )

    async def _choose_diff_change(
        self, tool: AuditTool, diff_text: str, arguments: AuditToolArguments
    ) -> "_ChosenAuditInput":
        """Return the change ``diff_text`` describes, as ``tool`` audits it."""
        _check_diff_text_size(diff_text)
        if tool.diff_scope_kind is DiffScopeKind.CHANGED_DIRECTORIES:
            directories = await read_changed_directories_scope(
                diff_text, self._working_directory, CODE_IGNORED_NAMES
            )
            return _ChosenAuditInput(
                audit_input=directories.audit_input,
                unit_selector=directories.unit_selector,
                diff_change=directories,
            )
        if tool.diff_scope_kind is DiffScopeKind.NONE:
            raise ValueError(f"{tool.name} takes no diff_text")
        diff_change = await read_diff_change_scope(
            diff_text, arguments.diff_units or DiffUnits.UNITS, self._working_directory
        )
        return _ChosenAuditInput(
            audit_input=diff_change.scope.audit_input,
            unit_selector=diff_change.scope.unit_selector,
            diff_change=diff_change,
        )


@dataclass(frozen=True)
class _ChosenAuditInput:
    """What one call audits: a path, the staged change, or a diff's change.

    unit_selector keeps the units of the change; None for a path. staged is
    the staged change, and diff_change the change a diff describes, when
    the call audits that.
    """

    audit_input: AuditInput
    unit_selector: BaseUnitSelector | None = None
    staged: StagedChangeScope | None = None
    diff_change: DiffChangeScope | ChangedDirectoriesScope | None = None


def _check_diff_text_size(diff_text: str) -> None:
    """Raise ToolError when ``diff_text`` is over the limit."""
    size = len(diff_text.encode("utf-8"))
    if size > MAX_DIFF_TEXT_BYTES:
        raise ToolError(
            f"diff_text is {size} bytes, over the limit of 2 MB "
            f"({MAX_DIFF_TEXT_BYTES} bytes); audit a smaller diff"
        )


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
