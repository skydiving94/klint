"""One audit tool: its name, the kind of audit it runs, and how it audits a diff."""

from dataclasses import dataclass
from enum import Enum

from klint.catalog.change_summary import CHANGE_SUMMARY_KIND_ID
from klint.catalog.code import FILE_CONTENTS_KIND_ID, PROJECT_STRUCTURE_KIND_ID


class DiffScopeKind(Enum):
    """What an audit tool audits of a diff it is given."""

    NONE = "none"
    CHANGED_UNITS = "changed_units"
    CHANGED_DIRECTORIES = "changed_directories"


@dataclass(frozen=True)
class AuditTool:
    """An MCP tool that runs one kind of audit.

    name is the tool's name. audit_kind_id names the kind of audit, as a
    suite offers it. diff_scope_kind is what it audits of a diff: the units
    on its changed lines, as `klint --diff-from` does, or the directories
    that hold its changed files, as `klint-structure --diff-from` does.
    """

    name: str
    audit_kind_id: str
    diff_scope_kind: DiffScopeKind = DiffScopeKind.NONE


FILE_AUDIT_TOOL = AuditTool(
    name="audit_files",
    audit_kind_id=FILE_CONTENTS_KIND_ID,
    diff_scope_kind=DiffScopeKind.CHANGED_UNITS,
)
STRUCTURE_AUDIT_TOOL = AuditTool(
    name="audit_structure",
    audit_kind_id=PROJECT_STRUCTURE_KIND_ID,
    diff_scope_kind=DiffScopeKind.CHANGED_DIRECTORIES,
)
CHANGE_SUMMARY_TOOL = AuditTool(
    name="check_change_summary",
    audit_kind_id=CHANGE_SUMMARY_KIND_ID,
)
