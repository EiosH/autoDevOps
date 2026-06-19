from tools.registry import ToolRegistry
from core.models import ToolCallRecord, TaskStatus
from time import time


class ToolExecutor():
    registry: ToolRegistry

    def __init__(self, registry: ToolRegistry) -> None:
        self.registry = registry

    def execute(self, tool_name: str, **kwargs):
        tool = self.registry.get(tool_name)
        started_at = time()
        try:
            result = tool.run(**kwargs)
            finished_at = time()
            return ToolCallRecord(tool_name=tool_name,
                                  arguments=kwargs,
                                  result=result,
                                  status=TaskStatus.SUCCESS,
                                  started_at=started_at,
                                  finished_at=finished_at)
        except Exception as e:
            finished_at = time()
            return ToolCallRecord(tool_name=tool_name,
                                  arguments=kwargs,
                                  status=TaskStatus.FAILED,
                                  started_at=started_at,
                                  finished_at=finished_at,
                                  error=str(e))
