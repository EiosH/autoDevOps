from __future__ import annotations

from abc import abstractmethod

from core.models import SkillSpec
from engine.llm import LLMProvider
from protocols.mcp.client import McpClient
from skills.base import BaseSkill, SkillResult
from skills.prompt_loop import run_prompt_skill_loop


class PromptSkill(BaseSkill):
    """
    Prompt-based skill: the LLM chooses MCP tools via function calling.

    Each skill MUST declare allowed_tools — only those MCP tools are
    discovered and exposed to the model for this skill invocation.
    """

    allowed_tools: list[str]
    system_prompt: str
    finish_schema: dict
    max_steps: int = 15

    def __init__(self, spec: SkillSpec) -> None:
        if not self.allowed_tools:
            raise ValueError(f"{type(self).__name__} must define allowed_tools")
        self.spec = spec
        self.spec.allowed_tools = list(self.allowed_tools)

    @abstractmethod
    def build_user_message(self, **kwargs) -> str:
        """Turn skill arguments into the user message for the tool loop."""

    def execute(
        self,
        mcp: McpClient,
        llm: LLMProvider,
        **kwargs,
    ) -> SkillResult:
        return run_prompt_skill_loop(
            llm=llm,
            mcp=mcp,
            allowed_tools=list(self.allowed_tools),
            system_prompt=self.system_prompt,
            user_message=self.build_user_message(**kwargs),
            finish_schema=self.finish_schema,
            max_steps=self.max_steps,
        )
