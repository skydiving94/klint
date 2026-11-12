"""How much of a file, class or function each judge is shown."""

from klint.core.models.audits import DEFAULT_CHARACTER_BUDGET

# The most characters of a file, class or function unit each known judge is
# shown, by the model name the judge settings give it, as measured on the
# code-unit accuracy set in judge_accuracy/code_units/. Kev-4B catches too
# few problems for a longer text to keep its accuracy. Kev-9B keeps its
# accuracy up to 8,000. Jev keeps it up to 12,000, the longest length the set
# measures; past that, its budget stays well within the 32,000 tokens it
# accepts per request.
model_name_to_character_budget = {
    "jaredpalmer/kev-4b": DEFAULT_CHARACTER_BUDGET,
    "jaredpalmer/kev-9b": 8_000,
    "jev-latest": 60_000,
}


def find_judge_character_budget(model_name: str) -> int:
    """Return the most characters of a code unit the judge ``model_name`` is shown.

    A judge not measured is shown the default budget.
    """
    return model_name_to_character_budget.get(model_name, DEFAULT_CHARACTER_BUDGET)
