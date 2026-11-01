"""The text the judge reads about a summary: its evidence, then the summary."""

from collections.abc import Sequence

from klint.catalog.change_summary.document import ChangeKind
from klint.catalog.domain_neutral.renderers.character_budget import (
    join_lines_within_budget,
)

# The fewest characters worth giving the premise; with less room, it is left
# out and the judge is told so.
_LEAST_PREMISE_BUDGET = 200


def join_premise_and_hypothesis(
    premise_lines: Sequence[str],
    hypothesis: str,
    character_budget: int,
    what_premise_describes: str,
) -> str:
    """Return the premise lines, a blank line, then the hypothesis.

    The hypothesis is the summary judged, and the premise its evidence. The
    text holds at most ``character_budget`` characters: lines are left out
    of the end of the premise first, and its last line says how many lines
    of ``what_premise_describes`` were left out. A hypothesis too long to
    leave the premise room is shown alone, cut to fit, after a premise line
    saying that it was left out.
    """
    hypothesis_line = f"Hypothesis: {hypothesis}"
    premise_budget = character_budget - len(hypothesis_line) - 2
    if premise_budget < _LEAST_PREMISE_BUDGET:
        premise = (
            f"Premise: {what_premise_describes}, left out: the hypothesis takes "
            f"up the {character_budget} characters there is room for."
        )
        hypothesis_text = join_lines_within_budget(
            [hypothesis_line],
            max(character_budget - len(premise) - 2, 0),
            "the hypothesis",
            stated_budget=character_budget,
        )
        return f"{premise}\n\n{hypothesis_text}"[:character_budget]
    premise = join_lines_within_budget(
        premise_lines,
        premise_budget,
        what_premise_describes,
        stated_budget=character_budget,
    )
    return f"{premise}\n\n{hypothesis_line}"


def count_items(count: int, item_name: str) -> str:
    """Return ``count`` with ``item_name``, plural unless the count is 1."""
    return f"{count} {item_name}" if count == 1 else f"{count} {item_name}s"


def describe_file_change(change_kind: ChangeKind, old_path: str | None) -> str:
    """Return what the change does to a file: "modified", "renamed from <path>"."""
    if change_kind is ChangeKind.RENAMED and old_path is not None:
        return f"renamed from {old_path}"
    return change_kind.value
