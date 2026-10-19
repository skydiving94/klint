"""The set of answers a judge can choose between for a rule."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Choice:
    """One possible answer.

    key is the name exchanged with the judge, label is what reports show, and
    criterion tells the judge when to pick it. is_finding marks an answer
    that counts as a problem; priority orders answers in a report, lowest
    first.
    """

    key: str
    label: str
    criterion: str
    is_finding: bool = False
    priority: int = 0


@dataclass(frozen=True)
class AnswerScale:
    """A named, ordered set of choices."""

    name: str
    choices: tuple[Choice, ...]

    def criteria_payload(self) -> dict[str, str]:
        """Return each choice's criterion keyed by its key, in scale order."""
        return {choice.key: choice.criterion for choice in self.choices}

    def choice(self, key: str) -> Choice:
        """Return the choice for ``key``, ignoring case; raise KeyError if unknown."""
        wanted = key.lower()
        for choice in self.choices:
            if choice.key == wanted:
                return choice
        raise KeyError(key)
