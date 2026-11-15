"""Scores of the judge on the code-unit set: by length, and the budget they give."""

from collections.abc import Callable, Sequence
from dataclasses import dataclass

from judge_accuracy.code_units.judged_unit import JudgedUnit
from judge_accuracy.code_units.length_bands import (
    BASELINE_LENGTH,
    LENGTH_BANDS,
    LengthBand,
)

# The margin: a band keeps at least this share of the catch rate below the
# baseline length...
KEPT_CATCH_SHARE = 0.95
# ...and wrongly flags at most this much more of its true units.
ALLOWED_FALSE_FLAG_RISE = 0.02


@dataclass(frozen=True)
class GroupScore:
    """How the judge did on one group of units, the refused ones left out.

    planted_count and true_count count the units answered about.
    """

    planted_count: int
    caught_count: int
    caught_by_own_check_count: int
    true_count: int
    flagged_count: int
    refused_count: int

    def find_catch_rate(self) -> float:
        return self.caught_count / self.planted_count if self.planted_count else 0.0

    def find_false_flag_rate(self) -> float:
        return self.flagged_count / self.true_count if self.true_count else 0.0


@dataclass(frozen=True)
class BandVerdict:
    """A band above the baseline, its score, and whether it meets the margin.

    shortfall says why it does not; empty when it does.
    """

    band: LengthBand
    score: GroupScore
    shortfall: str

    def does_meet_margin(self) -> bool:
        return not self.shortfall


@dataclass(frozen=True)
class BudgetChoice:
    """The budget the margin gives at one threshold, and how it was reached.

    verdicts are the bands above the baseline, in order, up to the first
    that does not meet the margin.
    """

    min_confidence: float
    baseline: GroupScore
    verdicts: tuple[BandVerdict, ...]
    character_budget: int


def score_units(units: Sequence[JudgedUnit], min_confidence: float) -> GroupScore:
    answered = [unit for unit in units if not unit.is_refused()]
    planted = [unit for unit in answered if not unit.is_true()]
    true = [unit for unit in answered if unit.is_true()]
    return GroupScore(
        planted_count=len(planted),
        caught_count=sum(unit.is_flagged(min_confidence) for unit in planted),
        caught_by_own_check_count=sum(
            unit.is_caught_by_own_check(min_confidence) for unit in planted
        ),
        true_count=len(true),
        flagged_count=sum(unit.is_flagged(min_confidence) for unit in true),
        refused_count=len(units) - len(answered),
    )


def score_band(
    units: Sequence[JudgedUnit], band: LengthBand, min_confidence: float
) -> GroupScore:
    return score_units(_select(units, band.does_hold), min_confidence)


def choose_budget(
    units: Sequence[JudgedUnit],
    min_confidence: float,
    bands: Sequence[LengthBand] = LENGTH_BANDS,
) -> BudgetChoice:
    """Return the longest length up to which every band meets the margin.

    The baseline is every unit below the baseline length. A band meets the
    margin when it catches at least KEPT_CATCH_SHARE of the baseline's catch
    rate and wrongly flags at most ALLOWED_FALSE_FLAG_RISE more of its true
    units. The budget is the upper length of the last band, going up from
    the baseline, before one that does not, or that has no planted or no
    true unit; the baseline length when the first one does not.
    """
    baseline = score_units(
        _select(units, lambda length: length < BASELINE_LENGTH), min_confidence
    )
    verdicts: list[BandVerdict] = []
    character_budget = BASELINE_LENGTH
    for band in bands:
        if band.is_below_baseline():
            continue
        score = score_band(units, band, min_confidence)
        verdict = BandVerdict(
            band=band, score=score, shortfall=_find_shortfall(score, baseline)
        )
        verdicts.append(verdict)
        if not verdict.does_meet_margin():
            break
        character_budget = band.upper_length
    return BudgetChoice(
        min_confidence=min_confidence,
        baseline=baseline,
        verdicts=tuple(verdicts),
        character_budget=character_budget,
    )


def _find_shortfall(score: GroupScore, baseline: GroupScore) -> str:
    """Return why ``score`` misses the margin over ``baseline``; "" if it does not."""
    if score.planted_count == 0 or score.true_count == 0:
        return "no planted or no true unit"
    reasons: list[str] = []
    least_catch_rate = KEPT_CATCH_SHARE * baseline.find_catch_rate()
    if score.find_catch_rate() < least_catch_rate:
        reasons.append(
            f"catches {score.find_catch_rate():.1%}, below {least_catch_rate:.1%}"
        )
    most_false_flag_rate = baseline.find_false_flag_rate() + ALLOWED_FALSE_FLAG_RISE
    if score.find_false_flag_rate() > most_false_flag_rate:
        reasons.append(
            f"flags {score.find_false_flag_rate():.1%} of true units, "
            f"above {most_false_flag_rate:.1%}"
        )
    return "; ".join(reasons)


def _select(
    units: Sequence[JudgedUnit], does_hold_length: Callable[[int], bool]
) -> list[JudgedUnit]:
    return [unit for unit in units if does_hold_length(unit.length)]
