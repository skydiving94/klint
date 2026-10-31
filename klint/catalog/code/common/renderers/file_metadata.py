from klint.catalog.code.common.units.file_metadata import AuditableFileMetadataUnit
from klint.catalog.common.renderers.character_budget import join_lines_within_budget
from klint.core.interfaces.renderer import BaseUnitRenderer
from klint.core.models.render_input import RenderInput


class FileMetadataRenderer(BaseUnitRenderer):
    """Shows the judge what was read from a file, in one line."""

    def render_subject(self, render_input: RenderInput) -> str:
        description = describe_file_metadata(
            render_input.get_unit_as(AuditableFileMetadataUnit)
        )
        return join_lines_within_budget(
            [description], render_input.character_budget, "the file's description"
        )


def describe_file_metadata(file_unit: AuditableFileMetadataUnit) -> str:
    """Return one line naming the file and what was read from it.

    A binary file is named only. A file that cannot be parsed is named with
    its line count and marked so, since what it holds is unknown.
    """
    if file_unit.line_count is None:
        return f"{file_unit.file_name} (binary)"
    details: list[str] = [f"lines={file_unit.line_count}"]
    if file_unit.is_unparseable:
        details.append("cannot be parsed")
    if file_unit.exports:
        details.append(f"exports=[{', '.join(file_unit.exports)}]")
    if file_unit.imports:
        details.append(f"imports=[{', '.join(file_unit.imports)}]")
    if file_unit.classes:
        details.append(f"classes=[{', '.join(file_unit.classes)}]")
    if file_unit.functions:
        details.append(f"functions=[{', '.join(file_unit.functions)}]")
    return f"{file_unit.file_name} ({'; '.join(details)})"
