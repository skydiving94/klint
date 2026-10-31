from abc import ABC, abstractmethod

from klint.core.models.render_input import RenderInput


class BaseUnitRenderer(ABC):
    """Writes the text the judge reads about a unit: the subject of its questions.

    A suite chooses the evidence each kind of unit shows the judge by the
    renderer it gives that kind of unit.
    """

    @abstractmethod
    def render_subject(self, render_input: RenderInput) -> str:
        """Return the text the judge reads about ``render_input.unit``.

        The text holds at most ``render_input.character_budget`` characters.
        A renderer that leaves something out to stay within them ends the
        text with a line saying what it left out. Raises TypeError when this
        renderer cannot describe such a unit.
        """
