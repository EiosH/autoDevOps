from agents.base import BaseAgent
from core.agent_runner import AgentRunner
from core.models import (
    AgentCard,
    AgentResult,
    AgentRole,
    RiskLevel,
    RunContext,
    Task,
    TaskStatus,
)
from engine.llm import LLMProvider
from tools.executor import ToolExecutor

REVIEW_SYSTEM_PROMPT = """You are a code review agent.

Use the provided tools to complete the task. The model will invoke tools natively.

Workflow:
1. git_diff — inspect all changes
2. read_file — read specific files if needed

Do NOT modify files. Review for correctness, maintainability, and completeness.
Mark approved=false if there are high-severity issues.
"""

REVIEW_FINISH_SCHEMA = {
    "type": "object",
    "properties": {
        "approved": {"type": "boolean"},
        "issues": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "severity": {
                        "type": "string",
                        "enum": ["high", "medium", "low"],
                    },
                    "file": {"type": "string"},
                    "comment": {"type": "string"},
                },
                "required": ["severity", "comment"],
            },
        },
        "summary": {"type": "string"},
    },
    "required": ["approved", "issues", "summary"],
}


class ReviewAgent(BaseAgent):
    llm: LLMProvider
    tool_executor: ToolExecutor
    runner: AgentRunner

    def __init__(
        self,
        llm: LLMProvider,
        tool_executor: ToolExecutor,
        runner: AgentRunner | None = None,
    ) -> None:
        self.llm = llm
        self.tool_executor = tool_executor
        self.runner = runner or AgentRunner()
        super().__init__(
            AgentCard(
                name="review_agent",
                role=AgentRole.REVIEW,
                capabilities=["code_review", "risk_analysis"],
                tools=["read_file", "git_diff"],
                risk_level=RiskLevel.LOW,
            )
        )

    def run(self, task: Task, ctx: RunContext) -> AgentResult:
        result = self.runner.run_loop(
            llm=self.llm,
            tool_executor=self.tool_executor,
            allowed_tools=self.card.tools,
            task=task,
            agent_name=self.card.name,
            system_prompt=REVIEW_SYSTEM_PROMPT,
            user_message=self.build_user_message(task, ctx),
            finish_schema=REVIEW_FINISH_SCHEMA,
            ctx=ctx,
        )
        if (
            result.status == TaskStatus.SUCCESS
            and result.output.get("approved") is False
        ):
            has_high = any(
                issue.get("severity") == "high"
                for issue in result.output.get("issues", [])
            )
            if has_high:
                result.status = TaskStatus.FAILED
        return result
