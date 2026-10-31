from klint.core.interfaces.renderer import BaseUnitRenderer
from klint.core.models.render_input import RenderInput


class UnitContentRenderer(BaseUnitRenderer):
    """Describes a unit with the text the unit gives of itself."""

    def render_subject(self, render_input: RenderInput) -> str:
        return render_input.unit.get_content()
