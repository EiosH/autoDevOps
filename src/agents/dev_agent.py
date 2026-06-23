from agents.base import BaseAgent
from core.agent_runner import AgentRunner
from core.models import AgentCard, AgentResult, AgentRole, RiskLevel, RunContext, Task
from engine.llm import LLMProvider
from skills.executor import SkillExecutor

DEV_SYSTEM_PROMPT = """You are a dev agent.

Choose skills to complete the task. You cannot call low-level tools directly.

Available skills:
- code_refactor: Refactor existing code — rewrite files, add files, delete files.
  Use for merging, splitting, moving logic, deleting files, or any change to existing code.
  Pass goal with all affected file paths
- code_write: Greenfield (0-to-1) only — never use for delete or merge tasks.

Workflow:
1. Check episodic memory for review_feedback — if present, fix all listed issues
2. Use short-term memory (recent tool calls) to avoid repeating failed actions
3. Pick code_write OR code_refactor based on the task
4. Return finish JSON with changed_files, deleted_files (if any), and summary
"""

DEV_FINISH_SCHEMA = {
    "type": "object",
    "properties": {
        "changed_files": {
            "type": "array",
            "items": {"type": "string"},
        },
        "deleted_files": {
            "type": "array",
            "items": {"type": "string"},
        },
        "summary": {"type": "string"},
    },
    "required": ["changed_files", "summary"],
}


class DevAgent(BaseAgent):
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
                name="dev_agent",
                role=AgentRole.DEV,
                capabilities=["code_generation"],
                skills=["code_write", "code_refactor"],
                risk_level=RiskLevel.MEDIUM,
            )
        )

    def run(self, task: Task, ctx: RunContext) -> AgentResult:
        return self.runner.run_loop(
            llm=self.llm,
            skill_executor=self.skill_executor,
            allowed_skills=self.card.skills,
            task=task,
            agent_name=self.card.name,
            system_prompt=DEV_SYSTEM_PROMPT,
            user_message=self.build_user_message(task, ctx),
            finish_schema=DEV_FINISH_SCHEMA,
            ctx=ctx,
        )
