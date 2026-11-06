"""What the hook tells the agent when it blocks a stop, and the user when it lets go."""

from collections.abc import Mapping, Sequence
from importlib import resources
from pathlib import Path

from klint.catalog.domain_neutral.git import GitChange, GitFileChange
from klint.cli.change_summary_stop_hook.summary_coverage import SummaryCoverage
from klint.core.models.reports import AuditFinding

# Where the agent writes its summaries, relative to the project directory.
SUMMARIES_PATH = Path(".klint/change-summary.json")
# The most files, or files and hunks, one list in a message names.
_MAX_LISTED_ITEMS = 60
_INSTRUCTIONS_RESOURCE = "change_summary_stop_hook/writing_change_summaries.md"


def load_summary_instructions() -> str:
    """Return the instructions for writing the summaries, as shipped with klint."""
    instructions = resources.files("klint.resources") / _INSTRUCTIONS_RESOURCE
    return instructions.read_text(encoding="utf-8").strip()


def describe_missing_summaries(change: GitChange) -> str:
    return _join_paragraphs(
        f"Before you stop, write summaries of your change to {SUMMARIES_PATH}, "
        "then stop again. klint checks them before you may stop.",
        _describe_change(change),
        load_summary_instructions(),
    )


def describe_uncovered_change(coverage: SummaryCoverage, change: GitChange) -> str:
    return _join_paragraphs(
        f"The summaries in {SUMMARIES_PATH} are not those of the current change. "
        "Write summaries of the current change there, then stop again.",
        _describe_parts("Not summarized", coverage.unnamed_parts),
        _describe_parts("Summarized but not in the change", coverage.stale_parts),
        _describe_change(change),
        load_summary_instructions(),
    )


def describe_other_change() -> str:
    return _join_paragraphs(
        f"The summaries in {SUMMARIES_PATH} must be of the uncommitted change: "
        'summaries only, with "git_change": {}. Write summaries of the current '
        "change there, then stop again.",
        load_summary_instructions(),
    )


def describe_unreadable_summaries(error: Exception) -> str:
    return _join_paragraphs(
        f"klint cannot read {SUMMARIES_PATH}: {error}\nFix the file, then stop again.",
        load_summary_instructions(),
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
        "commit. In each check, the summary is the hypothesis and its evidence "
        "the premise. A file, package or commit summary may name only what the "
        "summaries one level down name, such as the function a hunk changes. A "
        "summary above one you change may need to change too. Then stop again."
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


def _describe_change(change: GitChange) -> str:
    lines = [_describe_file(file) for file in change.files[:_MAX_LISTED_ITEMS]]
    more_count = len(change.files) - _MAX_LISTED_ITEMS
    if more_count > 0:
        lines.append(f"- and {more_count} more; see git status")
    return "\n".join(
        [
            f"The change ({change.diff_command}) holds these files and hunks:",
            *lines,
        ]
    )


def _describe_file(file: GitFileChange) -> str:
    kind = file.change_kind.value
    if file.old_path is not None:
        kind = f"{kind} from {file.old_path}"
    if file.is_binary:
        kind = f"{kind}, binary"
    headers = ", ".join(hunk.header.format_text() for hunk in file.hunks)
    return f"- {file.path} ({kind}): {headers or 'no hunk'}"


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
