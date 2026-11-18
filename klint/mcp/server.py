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

_DIFF_TEXT_HELP = (
    "diff_text is a unified diff in git's format, such as `gh pr diff` or "
    "`git diff main...HEAD` prints, up to 2 MB: its paths are taken as relative "
    "to the working directory, and each changed file there must match the "
    "diff's index lines."
)

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
            "and function. Give one of path, diff and diff_text. With diff, audit "
            "the staged change of the working directory's git repository; with "
            "diff_text, the change a diff describes. diff_units then chooses the "
            "units of each changed file: 'units' (the default) for the file and "
            "every function and class on a changed line, 'file' for the file "
            f"alone, 'all' for every unit. {_DIFF_TEXT_HELP} {_MIN_CONFIDENCE_HELP}"
        ),
    )
    async def audit_files(
        context: Context,
        path: str | None = None,
        diff: bool = False,
        diff_units: DiffUnits | None = None,
        diff_text: str | None = None,
        min_confidence: float = 0.0,
        all_answers: bool = False,
        rules_path: str | None = None,
    ) -> dict[str, object]:
        _check_one_input_is_given(path=path, diff=diff, diff_text=diff_text)
        if diff_units is not None and not (diff or diff_text is not None):
            raise ToolError("diff_units needs diff or diff_text")
        return await audits.run_audit(
            FILE_AUDIT_TOOL,
            AuditToolArguments(
                path=path,
                diff_units=diff_units or (DiffUnits.UNITS if diff else None),
                diff_text=diff_text,
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
            "rules: each directory, its layout and its imports. Give path or "
            "diff_text: with diff_text, audit the working directory as the "
            "project, but only each directory that holds a file the diff "
            f"changes, and its parents. {_DIFF_TEXT_HELP} {_MIN_CONFIDENCE_HELP}"
        ),
    )
    async def audit_structure(
        context: Context,
        path: str | None = None,
        diff_text: str | None = None,
        min_confidence: float = 0.0,
        all_answers: bool = False,
        rules_path: str | None = None,
    ) -> dict[str, object]:
        _check_one_input_is_given(path=path, diff_text=diff_text)
        return await audits.run_audit(
            STRUCTURE_AUDIT_TOOL,
            AuditToolArguments(
                path=path,
                diff_text=diff_text,
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
            "unit types it is asked about, and the languages and unit tags it is "
            "limited to. A later pack's definition replaces an earlier one's for "
            "the units both are for."
        ),
    )
    async def explain_rule(rule_id: str) -> dict[str, object]:
        return await rules.explain_rule(rule_id)

    return server


def _check_one_input_is_given(**name_to_value: str | bool | None) -> None:
    """Raise ToolError unless exactly one of the inputs is given.

    An input is given when it is neither None nor False.
    """
    given = [
        name for name, value in name_to_value.items() if value not in (None, False)
    ]
    names = " and ".join(name_to_value)
    if len(given) > 1:
        raise ToolError(
            f"{names} are mutually exclusive, and the call gives {', '.join(given)}: "
            "give one"
        )
    if not given:
        raise ToolError(f"One of {names} is required")


def run_mcp_server() -> int:
    """Serve the tools over stdio until the client closes the connection."""
    create_mcp_server(Path.cwd()).run("stdio")
    return 0
