from collections.abc import Mapping, Sequence

from klint.catalog.change_summary.renderers.premise_and_hypothesis import (
    describe_file_change,
    join_premise_and_hypothesis,
)
from klint.catalog.change_summary.renderers.summary_known_answers import (
    find_summary_known_answers,
)
from klint.catalog.change_summary.units import AuditableHunkSummaryUnit
from klint.core.interfaces import BaseUnitRenderer
from klint.core.models.audits import RenderInput


class HunkSummaryRenderer(BaseUnitRenderer):
    """Shows the judge a hunk's code as the premise and its summary as the hypothesis.

    The code is shown as a diff: the hunk's header, then each removed line
    after a "-" and each added line after a "+". Lines of code are left out
    of the end first to stay within the character budget. A hunk whose
    summary was left out is not shown: it fails the has_summary check.
    """

    def find_known_answers(
        self, render_input: RenderInput, rule_ids: Sequence[str]
    ) -> Mapping[str, str | None]:
        unit = render_input.get_unit_as(AuditableHunkSummaryUnit)
        return find_summary_known_answers(unit.hunk.summary, rule_ids)

    def render_subject(self, render_input: RenderInput) -> str:
        unit = render_input.get_unit_as(AuditableHunkSummaryUnit)
        hunk = unit.hunk
        change = describe_file_change(unit.file_change_kind, unit.file_old_path)
        premise_lines = [
            f"Premise: this code change to {unit.file_path} ({change}); a line "
            "starting with - is removed, with + is added.",
            hunk.header.format_text(),
            *(f"-{line}" for line in hunk.removed_lines),
            *(f"+{line}" for line in hunk.added_lines),
        ]
        return join_premise_and_hypothesis(
            premise_lines,
            hunk.summary,
            render_input.character_budget,
            "the code change",
        )
