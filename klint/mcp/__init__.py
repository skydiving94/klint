"""klint-mcp: klint's audits as MCP tools, served to one agent over stdio."""

from klint.mcp.server import create_mcp_server, run_mcp_server

__all__ = ["create_mcp_server", "run_mcp_server"]
