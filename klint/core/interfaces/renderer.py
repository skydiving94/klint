from abc import ABC, abstractmethod
from collections.abc import Mapping, Sequence

from klint.core.models.audits import RenderInput


class BaseUnitRenderer(ABC):
    """Writes the text the judge reads about a unit: the subject of its questions.

    A suite chooses the evidence each kind of unit shows the judge by the
    renderer it gives that kind of unit. A renderer may also answer a rule
    itself, when the unit settles the answer without the judge.
    """

    def find_known_answers(
        self, render_input: RenderInput, rule_ids: Sequence[str]
    ) -> Mapping[str, str | None]:
        """Return, by rule ID, the answers among ``rule_ids`` known without the judge.

        Each answer is the key of a choice on the kind's answer scale, or None
        for a rule the unit gives no answer to. The judge is asked only the
        rules left out, and is not asked at all when none is left. By default
        no answer is known.
        """
        del render_input, rule_ids
        return {}

    @abstractmethod
    def render_subject(self, render_input: RenderInput) -> str:
        """Return the text the judge reads about ``render_input.unit``.

        The text holds at most ``render_input.character_budget`` characters.
        A renderer that leaves something out to stay within them says what
        it left out in a line of the text, at the end of what was cut.
        Raises TypeError when this renderer cannot describe such a unit.
        """
