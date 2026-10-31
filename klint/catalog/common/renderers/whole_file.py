from klint.catalog.common.renderers.character_budget import join_lines_within_budget
from klint.catalog.common.units.file import AuditableFileUnit
from klint.core.interfaces.renderer import BaseUnitRenderer
from klint.core.models.render_input import RenderInput


class WholeFileRenderer(BaseUnitRenderer):
    """Shows the judge the text of a file: the whole of it when it fits.

    A file over the character budget is shown from its first line, as far
    as the budget goes.
    """

    def render_subject(self, render_input: RenderInput) -> str:
        content = render_input.get_unit_as(AuditableFileUnit).content
        return join_lines_within_budget(
            content.split("\n"), render_input.character_budget, "the file"
        )
