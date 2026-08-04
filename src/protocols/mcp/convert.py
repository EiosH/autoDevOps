from protocols.mcp.types import McpTool


def mcp_tools_to_openai(tools: list[McpTool]) -> list[dict]:
    """Convert MCP tool defs to OpenAI function-calling tool schemas."""
    return [
        {
            "type": "function",
            "function": {
                "name": tool.name,
                "description": tool.description,
                "parameters": tool.input_schema
                or {"type": "object", "properties": {}},
            },
        }
        for tool in tools
    ]
