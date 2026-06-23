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

TEST_SYSTEM_PROMPT = """You are a test agent.

Choose skills to complete the task. You cannot call low-level tools directly.

Available skills:
- run_test: Read source files and run pytest.
  Pass goal describing what to verify; optionally pass test_path.

Workflow:
1. Call run_test with a clear goal
2. Return finish JSON with passed and summary from the skill result
"""

TEST_FINISH_SCHEMA = {
    "type": "object",
    "properties": {
        "passed": {"type": "boolean"},
        "test_path": {"type": "string"},
        "summary": {"type": "string"},
    },
    "required": ["passed", "summary"],
}


class TestAgent(BaseAgent):
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
                name="test_agent",
                role=AgentRole.TEST,
                capabilities=["test_generation", "test_execution"],
                skills=["run_test"],
                risk_level=RiskLevel.MEDIUM,
            )
        )

    def run(self, task: Task, ctx: RunContext) -> AgentResult:
        result = self.runner.run_loop(
            llm=self.llm,
            skill_executor=self.skill_executor,
            allowed_skills=self.card.skills,
            task=task,
            agent_name=self.card.name,
            system_prompt=TEST_SYSTEM_PROMPT,
            user_message=self.build_user_message(task, ctx),
            finish_schema=TEST_FINISH_SCHEMA,
            ctx=ctx,
        )
        if result.status == TaskStatus.SUCCESS and result.output.get("passed") is False:
            result.status = TaskStatus.FAILED
        return result
