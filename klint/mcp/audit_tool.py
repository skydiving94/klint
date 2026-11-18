"""One audit tool: its name and the kind of audit it runs."""

from dataclasses import dataclass

from klint.catalog.change_summary import CHANGE_SUMMARY_KIND_ID
from klint.catalog.code import FILE_CONTENTS_KIND_ID, PROJECT_STRUCTURE_KIND_ID


@dataclass(frozen=True)
class AuditTool:
    """An MCP tool that runs one kind of audit.

    name is the tool's name. audit_kind_id names the kind of audit, as a
    suite offers it.
    """

    name: str
    audit_kind_id: str


FILE_AUDIT_TOOL = AuditTool(
    name="audit_files",
    audit_kind_id=FILE_CONTENTS_KIND_ID,
)
STRUCTURE_AUDIT_TOOL = AuditTool(
    name="audit_structure",
    audit_kind_id=PROJECT_STRUCTURE_KIND_ID,
)
CHANGE_SUMMARY_TOOL = AuditTool(
    name="check_change_summary",
    audit_kind_id=CHANGE_SUMMARY_KIND_ID,
)
