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
from skills.executor import SkillExecutor

REVIEW_SYSTEM_PROMPT = """You are a code review agent.

Choose skills to complete the task. You cannot call low-level tools directly.

Available skills:
- code_review: Inspect git diff and file contents, produce a review.
  Pass goal describing what to review.

Workflow:
1. Call code_review with a clear goal
2. Return finish JSON with approved, issues, and summary from the skill result
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
    skill_executor: SkillExecutor
    runner: AgentRunner

    def __init__(
        self,
        llm: LLMProvider,
        skill_executor: SkillExecutor,
        runner: AgentRunner | None = None,
    ) -> None:
        self.llm = llm
        self.skill_executor = skill_executor
        self.runner = runner or AgentRunner()
        super().__init__(
            AgentCard(
                name="review_agent",
                role=AgentRole.REVIEW,
                capabilities=["code_review", "risk_analysis"],
                skills=["code_review"],
                risk_level=RiskLevel.LOW,
            )
        )

    def run(self, task: Task, ctx: RunContext) -> AgentResult:
        result = self.runner.run_loop(
            llm=self.llm,
            skill_executor=self.skill_executor,
            allowed_skills=self.card.skills,
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
