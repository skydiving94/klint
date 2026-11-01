"""Renderers for the levels above the hunk: files and packages.

The judge reads the checked summaries one level down as the premise and the
level's own summary as the hypothesis; no code is shown at these levels.
"""

from klint.catalog.change_summary.document_reader import ROOT_PACKAGE_PATH
from klint.catalog.change_summary.renderers.child_summary_lines import (
    ChildSummary,
    list_child_summary_lines,
)
from klint.catalog.change_summary.renderers.premise_and_hypothesis import (
    count_items,
    describe_file_change,
    join_premise_and_hypothesis,
)
from klint.catalog.change_summary.units.file_summary import AuditableFileSummaryUnit
from klint.catalog.change_summary.units.package_summary import (
    AuditablePackageSummaryUnit,
)
from klint.core.interfaces.renderer import BaseUnitRenderer
from klint.core.models.render_input import RenderInput


class FileSummaryRenderer(BaseUnitRenderer):
    """Shows the judge a file's hunk summaries, then the file's summary.

    Each hunk summary says what its own checks found; one that failed is
    still shown, marked so.
    """

    def render_subject(self, render_input: RenderInput) -> str:
        unit = render_input.get_unit_as(AuditableFileSummaryUnit)
        change = describe_file_change(unit.change_kind, unit.old_path)
        if not unit.hunks:
            premise_lines = [
                f"Premise: the diff of the file {unit.path} ({change}) adds and "
                "removes no line, as for a binary file or a rename without edits."
            ]
        else:
            premise_lines = [
                f"Premise: summaries of the {count_items(len(unit.hunks), 'hunk')} "
                f"changed in the file {unit.path} ({change}).",
                *list_child_summary_lines(
                    [
                        ChildSummary(f"Hunk {number}", hunk.unit_id, hunk.hunk.summary)
                        for number, hunk in enumerate(unit.hunks, start=1)
                    ],
                    render_input.child_findings,
                ),
            ]
        return join_premise_and_hypothesis(
            premise_lines,
            unit.summary,
            render_input.character_budget,
            "the hunk summaries",
        )


class PackageSummaryRenderer(BaseUnitRenderer):
    """Shows the judge the summaries of a package's packages and files, then its own.

    The root package's summary is the commit's. Each summary one level down
    says what its own checks found; one that failed is still shown, marked
    so.
    """

    def render_subject(self, render_input: RenderInput) -> str:
        unit = render_input.get_unit_as(AuditablePackageSummaryUnit)
        children = [
            ChildSummary(
                f"Package {_find_relative_path(package.path, unit.path)}",
                package.unit_id,
                package.summary,
            )
            for package in unit.packages
        ] + [
            ChildSummary(
                f"File {_find_relative_path(file.path, unit.path)}",
                file.unit_id,
                file.summary,
            )
            for file in unit.files
        ]
        where = "the commit" if unit.is_root_package else f"the package {unit.path}"
        premise_lines = [
            f"Premise: summaries of the {_name_child_kinds(unit)} changed in {where}.",
            *list_child_summary_lines(children, render_input.child_findings),
        ]
        return join_premise_and_hypothesis(
            premise_lines,
            unit.summary,
            render_input.character_budget,
            "the summaries",
        )


def _find_relative_path(path: str, package_path: str) -> str:
    """Return ``path`` as seen from the package at ``package_path``."""
    if package_path == ROOT_PACKAGE_PATH:
        return path
    return path.removeprefix(f"{package_path}/")


def _name_child_kinds(package: AuditablePackageSummaryUnit) -> str:
    """Return what is inside ``package``: "packages", "files", or both."""
    if package.packages and package.files:
        return "packages and files"
    return "packages" if package.packages else "files"
