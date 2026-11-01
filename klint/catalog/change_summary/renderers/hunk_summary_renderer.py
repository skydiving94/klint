from klint.catalog.change_summary.renderers.premise_and_hypothesis import (
    describe_file_change,
    join_premise_and_hypothesis,
)
from klint.catalog.change_summary.units.hunk_summary_unit import (
    AuditableHunkSummaryUnit,
)
from klint.core.interfaces.renderer import BaseUnitRenderer
from klint.core.models.render_input import RenderInput


class HunkSummaryRenderer(BaseUnitRenderer):
    """Shows the judge a hunk's code as the premise and its summary as the hypothesis.

    The code is shown as a diff: the hunk's header, then each removed line
    after a "-" and each added line after a "+". Lines of code are left out
    of the end first to stay within the character budget.
    """

    def render_subject(self, render_input: RenderInput) -> str:
        unit = render_input.get_unit_as(AuditableHunkSummaryUnit)
        hunk = unit.hunk
        change = describe_file_change(unit.file_change_kind, unit.file_old_path)
        premise_lines = [
            f"Premise: this code change to {unit.file_path} ({change}); a line "
            "starting with - is removed, with + is added.",
            f"@@ -{_format_span(hunk.old_start, hunk.old_line_count)} "
            f"+{_format_span(hunk.new_start, hunk.new_line_count)} @@",
            *(f"-{line}" for line in hunk.removed_lines),
            *(f"+{line}" for line in hunk.added_lines),
        ]
        return join_premise_and_hypothesis(
            premise_lines,
            hunk.summary,
            render_input.character_budget,
            "the code change",
        )


def _format_span(start: int, line_count: int) -> str:
    """Return a side of a hunk header as git writes it: "40", or "40,3"."""
    return str(start) if line_count == 1 else f"{start},{line_count}"
