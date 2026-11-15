"""The klint-mcp server: its tools, and how it is started from the shell."""

from pathlib import Path

from mcp.server.mcpserver import Context, MCPServer
from mcp.server.mcpserver.exceptions import ToolError

from klint.app import BindingOverride
from klint.catalog.domain_neutral.git import DiffUnits
from klint.mcp.audit_runner import AuditToolArguments, AuditToolRunner
from klint.mcp.audit_tool import (
    CHANGE_SUMMARY_TOOL,
    FILE_AUDIT_TOOL,
    STRUCTURE_AUDIT_TOOL,
)
from klint.mcp.rule_tools import RuleToolRunner

SERVER_NAME = "klint"

_MIN_CONFIDENCE_HELP = (
    "min_confidence is the least confidence, 0.0 to 1.0, a finding needs to be "
    "reported; all_answers reports every answer, not the problems only; "
    "rules_path names a JSON file of custom rules that merge over the packs."
)


def create_mcp_server(
    working_directory: Path, *binding_overrides: BindingOverride
) -> MCPServer:
    """Return the server, with each tool bound to ``working_directory``.

    The tools audit paths inside that directory only. binding_overrides
    replace bindings of the audits, as for a test's judge.
    """
    audits = AuditToolRunner(working_directory, *binding_overrides)
    rules = RuleToolRunner(working_directory, *binding_overrides)
    server = MCPServer(
        SERVER_NAME,
        instructions=(
            "klint audits code with an LLM judge, which must already be running. "
            f"Each tool takes paths inside the working directory '{working_directory}' "
            "and returns the findings as the klint commands print them with --json, "
            "with the judge's usage under judge_usage."
        ),
    )

    @server.tool(
        name=FILE_AUDIT_TOOL.name,
        description=(
            "Audit the contents of a code file, or of every file under a "
            "directory, against the file rules: each file, and each Python class "
            "and function. With diff, audit the staged change of the working "
            "directory's git repository instead of a path; diff_units then "
            "chooses the units of each changed file: 'units' (the default) for "
            "the file and every function and class on a changed line, 'file' for "
            f"the file alone, 'all' for every unit. {_MIN_CONFIDENCE_HELP}"
        ),
    )
    async def audit_files(
        context: Context,
        path: str | None = None,
        diff: bool = False,
        diff_units: DiffUnits | None = None,
        min_confidence: float = 0.0,
        all_answers: bool = False,
        rules_path: str | None = None,
    ) -> dict[str, object]:
        return await audits.run_audit(
            FILE_AUDIT_TOOL,
            AuditToolArguments(
                path=path,
                diff_units=_read_diff_units(path, diff, diff_units),
                rules_path=rules_path,
                should_show_all_answers=all_answers,
                min_confidence=min_confidence,
            ),
            context,
        )

    @server.tool(
        name=STRUCTURE_AUDIT_TOOL.name,
        description=(
            "Audit the structure of a project directory against the structure "
            "rules: each directory, its layout and its imports. "
            f"{_MIN_CONFIDENCE_HELP}"
        ),
    )
    async def audit_structure(
        context: Context,
        path: str,
        min_confidence: float = 0.0,
        all_answers: bool = False,
        rules_path: str | None = None,
    ) -> dict[str, object]:
        return await audits.run_audit(
            STRUCTURE_AUDIT_TOOL,
            AuditToolArguments(
                path=path,
                rules_path=rules_path,
                should_show_all_answers=all_answers,
                min_confidence=min_confidence,
            ),
            context,
        )

    @server.tool(
        name=CHANGE_SUMMARY_TOOL.name,
        description=(
            "Check an agent's summaries of a change, in a change-summary JSON "
            "document: each hunk's summary against its code, and each file, "
            "package and commit summary against the summaries below it. "
            f"{_MIN_CONFIDENCE_HELP}"
        ),
    )
    async def check_change_summary(
        context: Context,
        path: str,
        min_confidence: float = 0.0,
        all_answers: bool = False,
        rules_path: str | None = None,
    ) -> dict[str, object]:
        return await audits.run_audit(
            CHANGE_SUMMARY_TOOL,
            AuditToolArguments(
                path=path,
                rules_path=rules_path,
                should_show_all_answers=all_answers,
                min_confidence=min_confidence,
            ),
            context,
        )

    @server.tool(
        description=(
            "List the rules an audit of a path would ask, each with the units it "
            "would be asked about: the file rules for a file, and both the file "
            "and the structure rules for a directory. No judge is asked. The "
            "project's exclusions apply, and are listed."
        ),
    )
    async def list_rules(path: str, rules_path: str | None = None) -> dict[str, object]:
        return await rules.list_rules(path, rules_path)

    @server.tool(
        description=(
            "Explain one rule: each pack that defines it, with its question, the "
            "unit types it is asked about, the languages and unit tags it is "
            "limited to, and the tool that asks it."
        ),
    )
    async def explain_rule(rule_id: str) -> dict[str, object]:
        return await rules.explain_rule(rule_id)

    return server


def _read_diff_units(
    path: str | None, diff: bool, diff_units: DiffUnits | None
) -> DiffUnits | None:
    """Return the units diff asks for; None without diff. Raises when they clash."""
    if diff:
        if path is not None:
            raise ToolError("diff takes no path: it audits the staged change")
        return diff_units or DiffUnits.UNITS
    if diff_units is not None:
        raise ToolError("diff_units needs diff")
    if path is None:
        raise ToolError("A path to audit, or diff, is required")
    return None


def run_mcp_server() -> int:
    """Serve the tools over stdio until the client closes the connection."""
    create_mcp_server(Path.cwd()).run("stdio")
    return 0
