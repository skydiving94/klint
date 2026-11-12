"""The report of a run on the code-unit set, written as Markdown to post on an issue."""

from collections.abc import Sequence
from dataclasses import dataclass

from judge_accuracy.code_units.judged_unit import CodeUnitType, JudgedUnit
from judge_accuracy.code_units.length_bands import BASELINE_LENGTH, LENGTH_BANDS
from judge_accuracy.code_units.scores import (
    ALLOWED_FALSE_FLAG_RISE,
    KEPT_CATCH_SHARE,
    BudgetChoice,
    GroupScore,
    choose_budget,
    score_band,
    score_units,
)

# The thresholds the budget is chosen at, beside the run's own.
BUDGET_THRESHOLDS = (0.0, 0.3, 0.5, 0.7, 0.8)


@dataclass(frozen=True)
class RunDescription:
    """What a run asked and of whom, for the report's opening lines.

    asked_request_count and asked_character_count are the requests sent to
    the judge and the characters of subject they held; reused_request_count
    those answered from memory.
    """

    judge_description: str
    case_set_name: str
    case_module_count: int
    min_confidence: float
    asked_request_count: int
    asked_character_count: int
    reused_request_count: int


def format_score_report(units: Sequence[JudgedUnit], run: RunDescription) -> str:
    """Return the Markdown report of ``units`` for the run ``run`` describes."""
    min_confidence = run.min_confidence
    whole = score_units(units, min_confidence)
    lines = [
        f"## Code-unit accuracy: {run.judge_description}",
        "",
        f"- Set: `{run.case_set_name}`, {run.case_module_count} case modules: "
        f"{sum(unit.is_true() for unit in units)} true units, "
        f"{sum(not unit.is_true() for unit in units)} planted ones, "
        "each shown to the judge whole.",
        f"- Min confidence: {min_confidence}. Refused: {whole.refused_count}.",
        f"- Judge requests: {run.asked_request_count} sent "
        f"({run.asked_character_count:,} characters of subject), "
        f"{run.reused_request_count} answered from memory.",
        f"- Margin: a band catches at least {KEPT_CATCH_SHARE:.0%} of the catch "
        f"rate below {BASELINE_LENGTH:,} characters, and wrongly flags at most "
        f"{ALLOWED_FALSE_FLAG_RISE * 100:.0f} points more of its true units.",
        "",
        "### Budget under the margin",
        "",
        "| Min confidence | Below the baseline: caught / wrongly flagged "
        "| Budget | Stopped by |",
        "| ---: | ---: | ---: | --- |",
        *(
            _format_budget_row(choose_budget(units, threshold))
            for threshold in sorted({*BUDGET_THRESHOLDS, min_confidence})
        ),
        "",
        "### By length",
        "",
        _TABLE_HEADER,
        _TABLE_RULE,
        *(
            _format_score_row(
                f"{band.describe()} characters",
                score_band(units, band, min_confidence),
            )
            for band in LENGTH_BANDS
        ),
        _format_score_row("Every length", whole),
        "",
        "### By kind of unit",
        "",
        _TABLE_HEADER,
        _TABLE_RULE,
        *(
            _format_score_row(
                f"{unit_type.value}, {group_name}",
                score_units(
                    [
                        unit
                        for unit in units
                        if unit.unit_type is unit_type
                        and (unit.length < BASELINE_LENGTH) == is_below
                    ],
                    min_confidence,
                ),
            )
            for unit_type in CodeUnitType
            for group_name, is_below in (
                (f"below {BASELINE_LENGTH:,}", True),
                (f"{BASELINE_LENGTH:,} and over", False),
            )
        ),
        "",
        *_format_unit_list(
            "Planted problems missed",
            [
                unit
                for unit in units
                if not unit.is_true()
                and not unit.is_refused()
                and not unit.is_flagged(min_confidence)
            ],
        ),
        *_format_unit_list(
            "True units wrongly flagged",
            [
                unit
                for unit in units
                if unit.is_true() and unit.is_flagged(min_confidence)
            ],
        ),
    ]
    return "\n".join(lines) + "\n"


_TABLE_HEADER = (
    "| Units | Planted | Caught | Caught by its own check | True "
    "| Wrongly flagged | Refused |"
)
_TABLE_RULE = "| --- | ---: | ---: | ---: | ---: | ---: | ---: |"


def _format_score_row(name: str, score: GroupScore) -> str:
    return (
        f"| {name} | {score.planted_count} "
        f"| {_format_share(score.caught_count, score.planted_count)} "
        f"| {_format_share(score.caught_by_own_check_count, score.planted_count)} "
        f"| {score.true_count} "
        f"| {_format_share(score.flagged_count, score.true_count)} "
        f"| {score.refused_count} |"
    )


def _format_budget_row(choice: BudgetChoice) -> str:
    baseline = choice.baseline
    stopping = [
        verdict for verdict in choice.verdicts if not verdict.does_meet_margin()
    ]
    stopped_by = (
        f"{stopping[0].band.describe()}: {stopping[0].shortfall}"
        if stopping
        else "every band measured meets it"
    )
    return (
        f"| {choice.min_confidence} "
        f"| {_format_share(baseline.caught_count, baseline.planted_count)} / "
        f"{_format_share(baseline.flagged_count, baseline.true_count)} "
        f"| {choice.character_budget:,} | {stopped_by} |"
    )


def _format_share(count: int, total: int) -> str:
    if total == 0:
        return "-"
    return f"{count}/{total} ({count / total:.0%})"


def _format_unit_list(title: str, units: Sequence[JudgedUnit]) -> list[str]:
    """Return a folded list of ``units``, longest first."""
    if not units:
        return []
    lines = [f"<details><summary>{title} ({len(units)})</summary>", ""]
    for unit in sorted(units, key=lambda unit: -unit.length):
        problem = unit.planted_problem
        planted = (
            "" if problem is None else f" (#{unit.planted_number}, {problem.rule_id})"
        )
        failures = unit.describe_failures()
        lines.append(
            f"- `{unit.unit_name}`{planted}, {unit.length:,} characters"
            + (f": failed {failures}" if failures else "")
        )
    return [*lines, "", "</details>", ""]
