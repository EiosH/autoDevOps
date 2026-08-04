"""MCP client: discover tools and call them."""

from __future__ import annotations

from typing import Protocol

from protocols.mcp.server import LocalMcpServer
from protocols.mcp.types import McpTool, McpToolResult


class McpClient(Protocol):
    def list_tools(self) -> list[McpTool]: ...

    def call_tool(self, name: str, arguments: dict | None = None) -> McpToolResult: ...


class LocalMcpClient:
    """In-process MCP client bound to a LocalMcpServer."""

    def __init__(self, server: LocalMcpServer) -> None:
        self._server = server

    def list_tools(self) -> list[McpTool]:
        return self._server.list_tools()

    def call_tool(self, name: str, arguments: dict | None = None) -> McpToolResult:
        return self._server.call_tool(name, arguments)
