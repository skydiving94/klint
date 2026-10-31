from klint.catalog.common.units.file import AuditableFileUnit
from klint.core.interfaces.renderer import BaseUnitRenderer
from klint.core.models.render_input import RenderInput


class WholeFileRenderer(BaseUnitRenderer):
    """Shows the judge the whole text of a file."""

    def render_subject(self, render_input: RenderInput) -> str:
        return render_input.get_unit_as(AuditableFileUnit).content
