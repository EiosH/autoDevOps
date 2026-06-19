from tools.base import BaseTool


class ToolNotFoundError(Exception):
    pass


class ToolRegistry():
    tools: list[BaseTool]

    def __init__(self) -> None:
        self.tools = []

    def register(self, tool: BaseTool):
        self.tools.append(tool)

    def get(self, name: str):
        for tool in self.tools:
            if tool.spec.name == name:
                return tool
        raise ToolNotFoundError(f"Tool with name '{name}' not found.")

    def list_tools(self):
        return [tool.spec for tool in self.tools]
