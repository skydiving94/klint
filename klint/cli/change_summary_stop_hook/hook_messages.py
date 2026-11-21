"""What the hook tells the agent when it blocks a stop, and the user when it lets go."""

from collections.abc import Mapping, Sequence

from klint.catalog.domain_neutral.git import GitChange
from klint.cli.change_summary_stop_hook.change_base import ChangeBase
from klint.cli.change_summary_stop_hook.summary_coverage import SummaryCoverage
from klint.cli.change_summary_writing import (
    SUMMARIES_PATH,
    InstructionsAudience,
    ListedFile,
    list_changed_files,
    load_summary_instructions,
)
from klint.core.models.reports import AuditFinding

# The most files, or files and hunks, one list in a message names.
_MAX_LISTED_ITEMS = 60


def _load_instructions() -> str:
    return load_summary_instructions(InstructionsAudience.STOP_HOOK)


def describe_missing_summaries(change: GitChange, base: ChangeBase) -> str:
    return _join_paragraphs(
        f"Before you stop, write summaries of your change to {SUMMARIES_PATH}, "
        "then stop again. klint checks them before you may stop.",
        _describe_change(change),
        _describe_git_change_field(base),
        _load_instructions(),
    )


def describe_uncovered_change(
    coverage: SummaryCoverage, change: GitChange, base: ChangeBase
) -> str:
    return _join_paragraphs(
        f"The summaries in {SUMMARIES_PATH} are not those of the current change. "
        "Write summaries of the current change there, then stop again.",
        _describe_parts("Not summarized", coverage.unnamed_parts),
        _describe_parts("Summarized but not in the change", coverage.stale_parts),
        _describe_change(change),
        _describe_git_change_field(base),
        _load_instructions(),
    )


def describe_other_change(base: ChangeBase) -> str:
    return _join_paragraphs(
        f"The summaries in {SUMMARIES_PATH} must be of the current change: "
        f'summaries only, with "git_change": {base.format_git_change()}. Write '
        "summaries of the current change there, then stop again.",
        _describe_git_change_field(base),
        _load_instructions(),
    )


def describe_unreadable_summaries(error: Exception) -> str:
    return _join_paragraphs(
        f"klint cannot read {SUMMARIES_PATH}: {error}\nFix the file, then stop again.",
        _load_instructions(),
    )


def describe_flagged_summaries(findings: Sequence[AuditFinding]) -> str:
    """Return the reason to fix the summaries klint flagged: each one and its checks."""
    unit_id_to_findings: dict[str, list[AuditFinding]] = {}
    for finding in findings:
        unit_id_to_findings.setdefault(finding.unit_id, []).append(finding)
    lines = [
        f"klint flagged {len(unit_id_to_findings)} of the summaries in "
        f"{SUMMARIES_PATH}. Rewrite each one so that it states only what its "
        "evidence shows and mentions every change it shows: the hunk's code for "
        "a hunk, the summaries one level down for a file, a package or the "
        "commit. Above the hunk, it may sum up those summaries in brief, but "
        "leaves none of them out. In each check, the summary is the hypothesis "
        "and its evidence the premise. A file, package or commit summary may "
        "name only what the summaries one level down name, such as the function "
        "a hunk changes. A summary above one you change may need to change too. "
        "Then stop again."
    ]
    for unit_findings in unit_id_to_findings.values():
        lines.append("")
        lines.append(_describe_summary(unit_findings[0]))
        lines.extend(_describe_failed_check(finding) for finding in unit_findings)
    return "\n".join(lines)


def describe_gave_up(max_blocks: int, reason: str) -> str:
    return (
        f"klint's change-summary stop hook blocked this session's stop "
        f"{max_blocks} times in a row, so it let the agent stop. What it said "
        f"last:\n{reason}"
    )


def describe_unverified(problem: str, judge_description: str | None) -> str:
    judge = "" if judge_description is None else f" Judge: {judge_description}."
    return (
        f"klint could not check the change summaries, so the agent may stop: "
        f"{problem}.{judge}"
    )


def _describe_summary(finding: AuditFinding) -> str:
    """Return a line naming the summary: its level, unit, place and text.

    The level and the text are read from the finding's context as JSON
    output gives it.
    """
    context = finding.convert_to_dict()["context"]
    level = summary = None
    if isinstance(context, Mapping):
        level = context.get("level")
        summary = context.get("summary")
    level_text = f"{level} summary" if isinstance(level, str) else "summary"
    place = "" if finding.location is None else f" at {finding.location.path}"
    text = f'"{summary}"' if isinstance(summary, str) else "no summary"
    return f"- The {level_text} of {finding.unit_id}{place}: {text}"


def _describe_failed_check(finding: AuditFinding) -> str:
    confidence = (
        "" if finding.confidence is None else f", {finding.confidence:.0%} confident"
    )
    return (
        f"  - {finding.rule_id}: {finding.answer.label}{confidence}. "
        f"Asked: {finding.question}"
    )


def _describe_git_change_field(base: ChangeBase) -> str:
    return (
        f'Name the change in the summaries as "git_change": '
        f"{base.format_git_change()}, which is {base.describe()}."
    )


def _describe_change(change: GitChange) -> str:
    listed_files = list_changed_files(change)
    lines = [_describe_file(file) for file in listed_files[:_MAX_LISTED_ITEMS]]
    more_count = len(listed_files) - _MAX_LISTED_ITEMS
    if more_count > 0:
        lines.append(f"- and {more_count} more; see git status")
    return "\n".join(
        [
            f"The change ({change.diff_command}) holds these files and hunks:",
            *lines,
        ]
    )


def _describe_file(file: ListedFile) -> str:
    headers = ", ".join(file.hunk_headers)
    return f"- {file.path} ({file.kind_description}): {headers or 'no hunk'}"


def _describe_parts(title: str, parts: Sequence[str]) -> str:
    if not parts:
        return ""
    lines = [f"- {part}" for part in parts[:_MAX_LISTED_ITEMS]]
    more_count = len(parts) - _MAX_LISTED_ITEMS
    if more_count > 0:
        lines.append(f"- and {more_count} more")
    return "\n".join([f"{title}:", *lines])


def _join_paragraphs(*paragraphs: str) -> str:
    return "\n\n".join(paragraph for paragraph in paragraphs if paragraph)
