"""In-process MCP server that exposes local ToolRegistry tools."""

from __future__ import annotations

from protocols.mcp.types import McpTool, McpToolResult
from tools.registry import ToolNotFoundError, ToolRegistry


class LocalMcpServer:
    """
    MCP-shaped server facade over existing BaseTool implementations.

    list_tools / call_tool mirror the MCP tools API so a LocalMcpClient
    (or a future stdio client) can discover and invoke tools uniformly.
    """

    def __init__(self, registry: ToolRegistry) -> None:
        self.registry = registry

    def list_tools(self) -> list[McpTool]:
        tools: list[McpTool] = []
        for tool in self.registry.tools:
            tools.append(
                McpTool(
                    name=tool.spec.name,
                    description=tool.spec.description,
                    input_schema=tool.spec.input_schema or {
                        "type": "object",
                        "properties": {},
                    },
                )
            )
        return tools

    def call_tool(self, name: str, arguments: dict | None = None) -> McpToolResult:
        arguments = arguments or {}
        try:
            tool = self.registry.get(name)
            result = tool.run(**arguments)
            return McpToolResult(content=result, is_error=False)
        except ToolNotFoundError as e:
            return McpToolResult(content=None, is_error=True, error=str(e))
        except Exception as e:
            return McpToolResult(content=None, is_error=True, error=str(e))
