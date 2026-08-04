from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from core.models import SkillSpec, ToolCallRecord
from engine.llm import LLMProvider
from protocols.mcp.client import McpClient


@dataclass
class SkillResult:
    success: bool
    output: dict
    error: str | None = None
    tool_calls: list[ToolCallRecord] = field(default_factory=list)


class BaseSkill(ABC):
    spec: SkillSpec

    @abstractmethod
    def execute(
        self,
        mcp: McpClient,
        llm: LLMProvider,
        **kwargs,
    ) -> SkillResult:
        pass
