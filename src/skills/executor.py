from time import time

from core.models import TaskStatus, ToolCallRecord
from engine.llm import LLMProvider
from protocols.mcp.client import McpClient
from skills.registry import SkillRegistry


class SkillExecutor:
    def __init__(
        self,
        registry: SkillRegistry,
        mcp: McpClient,
        llm: LLMProvider,
    ) -> None:
        self.registry = registry
        self.mcp = mcp
        self.llm = llm

    def execute(self, skill_name: str, **kwargs) -> tuple[ToolCallRecord, list[ToolCallRecord]]:
        skill = self.registry.get(skill_name)
        started_at = time()
        try:
            result = skill.execute(self.mcp, self.llm, **kwargs)
            finished_at = time()
            record = ToolCallRecord(
                tool_name=skill_name,
                arguments=kwargs,
                result=result.output,
                status=TaskStatus.SUCCESS if result.success else TaskStatus.FAILED,
                started_at=started_at,
                finished_at=finished_at,
                error=result.error,
            )
            return record, result.tool_calls
        except Exception as e:
            finished_at = time()
            record = ToolCallRecord(
                tool_name=skill_name,
                arguments=kwargs,
                status=TaskStatus.FAILED,
                started_at=started_at,
                finished_at=finished_at,
                error=str(e),
            )
            return record, []
