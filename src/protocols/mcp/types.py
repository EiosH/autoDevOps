from dataclasses import dataclass, field
from typing import Any


@dataclass
class McpTool:
    """MCP tools/list entry (subset used by this project)."""

    name: str
    description: str
    input_schema: dict[str, Any] = field(default_factory=dict)


@dataclass
class McpToolResult:
    """MCP tools/call result."""

    content: Any
    is_error: bool = False
    error: str | None = None
