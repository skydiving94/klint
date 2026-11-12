"""How much of a file, class or function each judge is shown."""

from klint.core.models.audits import DEFAULT_CHARACTER_BUDGET

# The most characters of a file, class or function unit each known judge is
# shown, by the model name the judge settings give it. Each is the longest
# length at which the judge still catches at least 95% of the problems it
# catches below 2,000 characters, with at most 2 points more false flags,
# measured on the code-unit accuracy set in judge_accuracy/code_units/.
model_name_to_character_budget = {
    "jaredpalmer/kev-4b": DEFAULT_CHARACTER_BUDGET,
    "jaredpalmer/kev-9b": DEFAULT_CHARACTER_BUDGET,
    "jev-latest": DEFAULT_CHARACTER_BUDGET,
}


def find_judge_character_budget(model_name: str) -> int:
    """Return the most characters of a code unit the judge ``model_name`` is shown.

    A judge not measured is shown the default budget.
    """
    return model_name_to_character_budget.get(model_name, DEFAULT_CHARACTER_BUDGET)
