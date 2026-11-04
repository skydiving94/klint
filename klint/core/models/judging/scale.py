"""The set of answers a judge can choose between for a rule."""

from dataclasses import dataclass


@dataclass(frozen=True)
class AnswerChoice:
    """One possible answer.

    key is the name exchanged with the judge, label is what reports show, and
    criterion tells the judge when to pick it. is_problem marks an answer
    that counts as a problem. sort_rank orders answers in a report, lowest
    first; a report may also style an answer by it.
    """

    key: str
    label: str
    criterion: str
    is_problem: bool = False
    sort_rank: int = 0


@dataclass(frozen=True)
class AnswerScale:
    """A named, ordered set of choices."""

    name: str
    choices: tuple[AnswerChoice, ...]

    def map_choice_key_to_criterion(self) -> dict[str, str]:
        """Return each choice's criterion keyed by its key, in scale order."""
        return {choice.key: choice.criterion for choice in self.choices}

    def find_choice(self, key: str) -> AnswerChoice:
        """Return the choice for ``key``, ignoring case; raise KeyError if unknown."""
        wanted = key.lower()
        for choice in self.choices:
            if choice.key == wanted:
                return choice
        raise KeyError(key)
