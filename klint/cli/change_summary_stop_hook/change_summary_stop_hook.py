"""The klint-change-summary-stop-hook command: a Stop hook for Claude Code.

It lets the agent stop once klint passes the agent's summaries of its
uncommitted change, and otherwise sends the agent back to write or fix them.
The hook prints its answer as JSON on stdout and always exits 0, so that a
failure of its own never keeps the agent going.
"""

import asyncio
import contextlib
import dataclasses
import os
import sys
from collections.abc import Sequence
from pathlib import Path

from klint.app import AppSettings, BindingOverride
from klint.app.pipeline import AuditPipeline, AuditRequest
from klint.catalog.change_summary import CHANGE_SUMMARY_KIND_ID
from klint.catalog.change_summary.documents import read_summaries_of_git_change
from klint.catalog.domain_neutral import JsonDocumentSourceFactory
from klint.catalog.domain_neutral.git import GitChange, GitChangeSource
from klint.cli.change_summary_stop_hook.block_count_store import BlockCountStore
from klint.cli.change_summary_stop_hook.hook_console import (
    STOP_HOOK_COMMAND_NAME,
    parse_min_confidence,
    print_hook_line,
    print_klint_warnings_raised_inside,
)
from klint.cli.change_summary_stop_hook.hook_messages import (
    SUMMARIES_PATH,
    describe_flagged_summaries,
    describe_gave_up,
    describe_missing_summaries,
    describe_other_change,
    describe_uncovered_change,
    describe_unreadable_summaries,
    describe_unverified,
)
from klint.cli.change_summary_stop_hook.stop_decision import StopDecision, StopVerdict
from klint.cli.change_summary_stop_hook.stop_event import StopEvent, read_stop_event
from klint.cli.change_summary_stop_hook.summary_coverage import (
    compare_summaries_with_change,
)
from klint.cli.change_summary_stop_hook.unit_failure_listener import (
    UnitFailureListener,
)
from klint.cli.wiring import create_command_injector
from klint.core.models.audits import DiskPathInput
from klint.core.models.reports import JsonValue

# The most stops in a row the hook blocks in one session; it lets the next
# one through, with a warning to the user.
MAX_BLOCKS_IN_A_ROW = 3
# The hook's own folder, which tells git to ignore everything in it.
_HOOK_FOLDER_IGNORE_PATH = SUMMARIES_PATH.parent / ".gitignore"


class ChangeSummaryStopHook:
    """Answers Stop events: lets the agent stop, or blocks it until its summaries pass.

    The judge and the rest are wired as for the klint commands; binding
    overrides replace or add bindings.
    """

    def __init__(self, *binding_overrides: BindingOverride) -> None:
        self._binding_overrides = binding_overrides

    async def respond(self, argv: Sequence[str], event_text: str) -> str:
        """Return what the hook prints for the Stop event ``event_text``.

        ``argv`` holds the hook's options. Any failure of the hook itself
        lets the agent stop, with a warning to the user.
        """
        try:
            min_confidence = parse_min_confidence(argv)
            event = read_stop_event(event_text, os.environ)
            with print_klint_warnings_raised_inside():
                decision = await self._decide(event, min_confidence)
        except Exception as error:
            decision = StopDecision.allow(
                describe_unverified(f"{type(error).__name__}: {error}", None)
            )
        return decision.format_hook_output()

    async def _decide(self, event: StopEvent, min_confidence: float) -> StopDecision:
        with contextlib.chdir(event.project_path):
            try:
                change = await _read_change()
                block_counts = BlockCountStore.open_for(Path.cwd())
            except ValueError as error:
                return StopDecision.allow(describe_unverified(str(error), None))
            decision = await self._check_summaries(change, min_confidence)
            return _cap_blocks_in_a_row(decision, event, block_counts)

    async def _check_summaries(
        self, change: GitChange, min_confidence: float
    ) -> StopDecision:
        if not change.files:
            return StopDecision.allow()
        if not SUMMARIES_PATH.exists():
            _create_hook_folder()
            return StopDecision.block(describe_missing_summaries(change))
        source = JsonDocumentSourceFactory().create_source(
            DiskPathInput(SUMMARIES_PATH)
        )
        try:
            raw_document = await source.read_input()
        except (OSError, ValueError) as error:
            return StopDecision.block(describe_unreadable_summaries(error))
        if not _is_of_uncommitted_change(raw_document):
            return StopDecision.block(describe_other_change())
        coverage = compare_summaries_with_change(raw_document, change)
        if not coverage.is_complete():
            return StopDecision.block(describe_uncovered_change(coverage, change))
        try:
            read_summaries_of_git_change(raw_document, change)
        except ValueError as error:
            return StopDecision.block(describe_unreadable_summaries(error))
        return await self._audit_summaries(min_confidence)

    async def _audit_summaries(self, min_confidence: float) -> StopDecision:
        try:
            settings = await asyncio.to_thread(AppSettings.from_env, SUMMARIES_PATH)
            injector = create_command_injector(settings, *self._binding_overrides)
            audit_pipeline = injector.get(AuditPipeline)
        except (OSError, ValueError) as error:
            return StopDecision.allow(describe_unverified(str(error), None))
        judge_description = settings.describe_judge()
        print_hook_line(f"Judge: {judge_description}")
        listener = UnitFailureListener()
        request = AuditRequest(
            audit_input=DiskPathInput(SUMMARIES_PATH),
            audit_kind_id=CHANGE_SUMMARY_KIND_ID,
            min_confidence=min_confidence,
            audit_progress_listener=listener,
        )
        try:
            # Only the hook's answer may reach stdout.
            with contextlib.redirect_stdout(sys.stderr):
                outcome = await audit_pipeline.run_audit(request)
        except Exception as error:
            return StopDecision.allow(
                describe_unverified(
                    f"{type(error).__name__}: {error}", judge_description
                )
            )
        failures = outcome.report.select_findings(min_confidence=min_confidence)
        unchecked = listener.describe_failures(len(outcome.selected_unit_ids))
        if failures:
            reason = describe_flagged_summaries(failures)
            return StopDecision.block(
                reason if unchecked is None else f"{reason}\n\n{unchecked}."
            )
        if unchecked is not None:
            return StopDecision.allow(describe_unverified(unchecked, judge_description))
        return StopDecision.allow()


def run_change_summary_stop_hook() -> int:
    """Answer the Stop event on stdin; always return exit status 0."""
    output = asyncio.run(
        ChangeSummaryStopHook().respond(sys.argv[1:], sys.stdin.read())
    )
    if output:
        print(output)
    return 0


async def _read_change() -> GitChange:
    """Return the uncommitted change of the current directory's repository.

    The summaries file is left out, as klint leaves it out of the change it
    checks the summaries against.
    """
    change = await GitChangeSource(Path.cwd()).read_input()
    summaries_path = SUMMARIES_PATH.resolve()
    repository_path = change.repository_path.resolve()
    if not summaries_path.is_relative_to(repository_path):
        return change
    relative_path = summaries_path.relative_to(repository_path).as_posix()
    return dataclasses.replace(
        change,
        files=tuple(
            file
            for file in change.files
            if relative_path not in (file.path, file.old_path)
        ),
    )


def _is_of_uncommitted_change(raw_document: JsonValue) -> bool:
    """Return True for summaries only whose git_change names no commit."""
    if not isinstance(raw_document, dict):
        return False
    git_change = raw_document.get("git_change")
    return isinstance(git_change, dict) and git_change.get("commit") is None


def _create_hook_folder() -> None:
    """Create the folder of the summaries, ignored by git with all it holds."""
    SUMMARIES_PATH.parent.mkdir(parents=True, exist_ok=True)
    if not _HOOK_FOLDER_IGNORE_PATH.exists():
        _HOOK_FOLDER_IGNORE_PATH.write_text(
            f"# Written by {STOP_HOOK_COMMAND_NAME}: git ignores this folder.\n*\n",
            encoding="utf-8",
        )


def _cap_blocks_in_a_row(
    decision: StopDecision, event: StopEvent, block_counts: BlockCountStore
) -> StopDecision:
    """Return ``decision``, or a stop with a warning once blocks reach the cap.

    A stop that does not follow a Stop hook's block starts the count again.
    """
    if decision.verdict is StopVerdict.ALLOW:
        block_counts.clear_count(event.session_id)
        return decision
    count = (
        block_counts.read_count(event.session_id) if event.is_stop_hook_active else 0
    )
    if count >= MAX_BLOCKS_IN_A_ROW:
        block_counts.clear_count(event.session_id)
        return StopDecision.allow(
            describe_gave_up(MAX_BLOCKS_IN_A_ROW, decision.message or "")
        )
    block_counts.write_count(event.session_id, count + 1)
    return decision


if __name__ == "__main__":
    sys.exit(run_change_summary_stop_hook())
