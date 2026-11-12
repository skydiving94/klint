"""The command that scores the judge the settings choose on the code-unit set.

Run it from the repository's root:

    uv run python -m judge_accuracy.code_units

The judge is chosen as for klint's commands, by the KLINT_JUDGE_* settings.
Every unit is shown to the judge whole, never cut to a budget. The report is
Markdown, printed on stdout; progress and refusals go to stderr.
"""

import argparse
import asyncio
import sys
import tempfile
from collections.abc import Sequence
from dataclasses import dataclass
from enum import IntEnum
from pathlib import Path

from injector import Module, provider, singleton

from judge_accuracy.change_summary.caching_judge import CachingJudge
from judge_accuracy.code_units.case_judging import CaseModuleJudging
from judge_accuracy.code_units.case_set import CaseModule, read_case_set
from judge_accuracy.code_units.judged_unit import JudgedUnit
from judge_accuracy.code_units.score_report import RunDescription, format_score_report
from klint.app import AppSettings, AuditKindRegistry, BindingOverride
from klint.app.pipeline import AuditPipeline
from klint.catalog.code import FILE_CONTENTS_KIND_ID
from klint.cli import create_command_injector
from klint.core import Auditor
from klint.core.interfaces import BaseJudge

COMMAND_NAME = "judge-accuracy"
# The set kept in the repository, used when no other is named.
DEFAULT_CASE_SET = Path(__file__).parent / "cases"
# A budget no unit of the set reaches, so that each is shown whole.
_WHOLE_UNIT_CHARACTER_BUDGET = 10**9
_LINE_PREFIX = f"[{COMMAND_NAME}]"


class ScoringExitCode(IntEnum):
    """How the command ends: 0 once the set is scored, 2 when it cannot be."""

    SCORED = 0
    RUN_ERROR = 2


@dataclass(frozen=True)
class ScoringArguments:
    """A command line, parsed: the set to score and the confidence to score at."""

    case_set: Path
    min_confidence: float


class _CachingJudgeBinding(Module):
    """Makes every audit ask the judge through one CachingJudge."""

    @singleton
    @provider
    def provide_caching_judge(self, judge: BaseJudge) -> CachingJudge:
        return CachingJudge(judge)

    @provider
    def provide_auditor(self, judge: CachingJudge) -> Auditor:
        return Auditor(judge)


def parse_scoring_arguments(argv: Sequence[str] | None = None) -> ScoringArguments:
    parser = argparse.ArgumentParser(
        prog="python -m judge_accuracy.code_units",
        description=(
            "Scores the judge the KLINT_JUDGE_* settings choose on a set of true "
            "and planted files, classes and functions, by their length, and "
            "prints the scores as Markdown"
        ),
        epilog=(
            f"Exit status: {ScoringExitCode.SCORED.value} once the set is scored, "
            f"{ScoringExitCode.RUN_ERROR.value} when it cannot be."
        ),
    )
    parser.add_argument(
        "case_set",
        nargs="?",
        type=Path,
        default=DEFAULT_CASE_SET,
        help="Folder of case modules to score on; the repository's set by default",
    )
    parser.add_argument(
        "--min-confidence",
        type=float,
        default=0.0,
        help="Least confidence a failed check needs to count (0.0 to 1.0)",
    )
    namespace = parser.parse_args(argv)
    return ScoringArguments(
        case_set=namespace.case_set, min_confidence=namespace.min_confidence
    )


async def run_scoring(
    argv: Sequence[str] | None = None, *binding_overrides: BindingOverride
) -> ScoringExitCode:
    """Score the judge on the set ``argv`` names; print the report.

    Binding overrides add or replace bindings, as for klint's commands.
    """
    arguments = parse_scoring_arguments(argv)
    try:
        case_modules = read_case_set(arguments.case_set)
        settings = AppSettings.from_env(arguments.case_set)
        injector = create_command_injector(
            settings,
            *binding_overrides,
            _CachingJudgeBinding(),
            code_character_budget=_WHOLE_UNIT_CHARACTER_BUDGET,
        )
        judge = injector.get(CachingJudge)
        audit_pipeline = injector.get(AuditPipeline)
        audit_kind = injector.get(AuditKindRegistry).find_audit_kind(
            FILE_CONTENTS_KIND_ID
        )
    except (OSError, ValueError) as error:
        _print_error_line(error)
        return ScoringExitCode.RUN_ERROR
    print(f"{_LINE_PREFIX} Judge: {settings.describe_judge()}", file=sys.stderr)
    with tempfile.TemporaryDirectory(prefix="klint-code-units-") as work_folder:
        judging = CaseModuleJudging(
            audit_pipeline, audit_kind, Path(work_folder), _LINE_PREFIX
        )
        judged = await _judge_case_modules(judging, case_modules)
    if judged is None:
        return ScoringExitCode.RUN_ERROR
    if all(unit.is_refused() for unit in judged):
        _print_error_line("The judge refused every unit of the set")
        return ScoringExitCode.RUN_ERROR
    print(
        format_score_report(
            judged,
            RunDescription(
                judge_description=settings.describe_judge(),
                case_set_name=_name_case_set(arguments.case_set),
                case_module_count=len(case_modules),
                min_confidence=arguments.min_confidence,
                asked_request_count=judge.count_asked_requests(),
                asked_character_count=judge.count_asked_characters(),
                reused_request_count=judge.count_reused_requests(),
            ),
        ),
        end="",
    )
    return ScoringExitCode.SCORED


def run_scoring_from_shell() -> int:
    """Run the command with the arguments the shell passed; return the exit code."""
    return asyncio.run(run_scoring(sys.argv[1:]))


async def _judge_case_modules(
    judging: CaseModuleJudging, case_modules: Sequence[CaseModule]
) -> list[JudgedUnit] | None:
    """Return every judged unit of ``case_modules``; None when one cannot be read."""
    judged: list[JudgedUnit] = []
    for case_module in case_modules:
        try:
            judged_in_module = await judging.judge_case_module(case_module)
        except (OSError, ValueError) as error:
            _print_error_line(f"{case_module.name}: {error}")
            return None
        judged.extend(judged_in_module)
        print(
            f"{_LINE_PREFIX} {case_module.name}: {len(judged_in_module)} units judged",
            file=sys.stderr,
        )
    return judged


def _name_case_set(case_set: Path) -> str:
    """Return the set's path from the current directory when it is inside it."""
    resolved = case_set.resolve()
    if resolved.is_relative_to(Path.cwd()):
        return resolved.relative_to(Path.cwd()).as_posix()
    return str(case_set)


def _print_error_line(reason: Exception | str) -> None:
    print(f"{_LINE_PREFIX} Error: {reason}", file=sys.stderr)
