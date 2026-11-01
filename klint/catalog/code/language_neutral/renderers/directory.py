from klint.catalog.code.language_neutral.renderers.file_metadata import (
    describe_file_metadata,
)
from klint.catalog.code.language_neutral.units.directory import AuditableDirectoryUnit
from klint.catalog.domain_neutral.renderers.character_budget import (
    join_lines_within_budget,
)
from klint.core.interfaces.renderer import BaseUnitRenderer
from klint.core.models.render_input import RenderInput


class DirectoryRenderer(BaseUnitRenderer):
    """Shows the judge a directory's tree, in a way that fits any language.

    The tree lists each directory's subdirectories and a line per file of
    what was read from it, the whole tree beneath the directory down, as far
    as the character budget goes.
    """

    def render_subject(self, render_input: RenderInput) -> str:
        directory = render_input.get_unit_as(AuditableDirectoryUnit)
        lines = [
            f"Target Directory Under Audit: {format_display_path(directory)}",
            f"Summary: {len(directory.files)} immediate files, "
            f"{len(directory.subdirectories)} immediate subdirectories",
            *list_tree_lines(directory),
        ]
        return join_lines_within_budget(
            lines, render_input.character_budget, "the tree"
        )


def format_display_path(directory: AuditableDirectoryUnit) -> str:
    """Return the path to show for ``directory``: its name when it is "."."""
    if directory.directory_path in (".", "./"):
        return directory.directory_name
    return directory.directory_path


def list_tree_lines(directory: AuditableDirectoryUnit, indent: int = 0) -> list[str]:
    """Return the lines describing the tree of ``directory``, indented ``indent``.

    Each directory lists its subdirectories and its files, then the trees of
    its subdirectories one level further in.
    """
    prefix = "  " * indent
    lines = [f"{prefix}Directory: {format_display_path(directory)}"]
    if directory.subdirectories:
        subdirectory_names = ", ".join(
            subdirectory.directory_name for subdirectory in directory.subdirectories
        )
        lines.append(f"{prefix}  Immediate Subdirectories: [{subdirectory_names}]")
    if directory.files:
        lines.append(f"{prefix}  Files:")
        lines.extend(
            f"{prefix}    - {describe_file_metadata(file_unit)}"
            for file_unit in directory.files
        )
    else:
        lines.append(f"{prefix}  Files: []")
    for subdirectory in directory.subdirectories:
        lines.extend(list_tree_lines(subdirectory, indent + 1))
    return lines
