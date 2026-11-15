"""The klint-mcp server: its tools, and how it is started from the shell."""

from pathlib import Path

from mcp.server.mcpserver import Context, MCPServer

from klint.app import BindingOverride
from klint.mcp.audit_runner import AuditToolArguments, AuditToolRunner
from klint.mcp.audit_tool import FILE_AUDIT_TOOL

SERVER_NAME = "klint"


def create_mcp_server(
    working_directory: Path, *binding_overrides: BindingOverride
) -> MCPServer:
    """Return the server, with each tool bound to ``working_directory``.

    The tools audit paths inside that directory only. binding_overrides
    replace bindings of the audits, as for a test's judge.
    """
    runner = AuditToolRunner(working_directory, *binding_overrides)
    server = MCPServer(
        SERVER_NAME,
        instructions=(
            "klint audits code with an LLM judge. Each tool takes paths inside "
            f"the working directory '{working_directory}' and returns the "
            "findings as the klint commands print them with --json, with the "
            "judge's usage."
        ),
    )

    @server.tool(
        description=(
            "Audit the contents of a code file, or of every file under a "
            "directory: each file, and each Python class and function, against "
            "the file rules."
        )
    )
    async def audit_files(path: str, context: Context) -> dict[str, object]:
        return await runner.run_audit(
            FILE_AUDIT_TOOL, AuditToolArguments(path=path), context
        )

    return server


def run_mcp_server() -> int:
    """Serve the tools over stdio until the client closes the connection."""
    create_mcp_server(Path.cwd()).run("stdio")
    return 0
