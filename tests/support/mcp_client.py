"""An in-process MCP client, for tests that call the tools of a klint-mcp server."""

import asyncio
from collections.abc import Mapping
from dataclasses import dataclass, field

from mcp.client._memory import InMemoryTransport
from mcp.client.session import ClientSession
from mcp.server.mcpserver import MCPServer
from mcp.types import CallToolResult, Tool


@dataclass(frozen=True)
class ProgressReport:
    """One progress notification, as the server sent it."""

    progress: float
    total: float | None
    message: str | None


@dataclass
class ToolCall:
    """What one call of a tool gave back: its result and the progress reported."""

    result: CallToolResult
    progress_reports: list[ProgressReport] = field(default_factory=list)


def call_tool(
    server: MCPServer, name: str, arguments: Mapping[str, object] | None = None
) -> ToolCall:
    """Call the tool ``name`` of ``server`` over an in-memory session."""
    return asyncio.run(_call_tool(server, name, dict(arguments or {})))


def list_tools(server: MCPServer) -> list[Tool]:
    """Return the tools ``server`` offers, as a client lists them."""
    return asyncio.run(_list_tools(server))


async def _call_tool(
    server: MCPServer, name: str, arguments: dict[str, object]
) -> ToolCall:
    call = ToolCall(result=CallToolResult(content=[]))

    async def record_progress(
        progress: float, total: float | None, message: str | None
    ) -> None:
        call.progress_reports.append(ProgressReport(progress, total, message))

    async with (
        InMemoryTransport(server) as (read_stream, write_stream),
        ClientSession(read_stream, write_stream) as session,
    ):
        await session.initialize()
        result = await session.call_tool(
            name, arguments, progress_callback=record_progress
        )
        assert isinstance(result, CallToolResult)
        call.result = result
    return call


async def _list_tools(server: MCPServer) -> list[Tool]:
    async with (
        InMemoryTransport(server) as (read_stream, write_stream),
        ClientSession(read_stream, write_stream) as session,
    ):
        await session.initialize()
        return list((await session.list_tools()).tools)
