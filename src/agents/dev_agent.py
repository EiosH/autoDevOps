from agents.base import BaseAgent
from core.agent_runner import AgentRunner
from core.models import AgentCard, AgentResult, AgentRole, RiskLevel, RunContext, Task
from engine.llm import LLMProvider
from tools.executor import ToolExecutor

DEV_SYSTEM_PROMPT = """You are a dev agent.

Mandatory workflow:
1. read_file — ALWAYS read target files before writing (even for new files, check if path exists)
2. write_patch — write COMPLETE runnable content; never leave placeholders
3. read_file — verify each written file is non-empty
4. git_diff — confirm changes

Completion rules (you MUST satisfy ALL before finish JSON):
- Every file listed in the goal must exist on disk
- You must have at least one successful write_patch per changed file
- For browser games: HTML must include game UI; JS must contain game logic (not just comments)
- Do NOT return finish JSON until verification reads succeed

If the goal mentions multiple files, write ALL of them in this task.

"""

DEV_FINISH_SCHEMA = {
    "type": "object",
    "properties": {
        "changed_files": {
            "type": "array",
            "items": {"type": "string"},
        },
        "summary": {"type": "string"},
    },
    "required": ["changed_files", "summary"],
}


class DevAgent(BaseAgent):
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
                name="dev_agent",
                role=AgentRole.DEV,
                capabilities=["code_generation"],
                tools=["read_file", "write_patch", "git_diff", "shell_exec"],
                risk_level=RiskLevel.MEDIUM,
            )
        )

    def run(self, task: Task, ctx: RunContext) -> AgentResult:
        return self.runner.run_loop(
            llm=self.llm,
            tool_executor=self.tool_executor,
            allowed_tools=self.card.tools,
            task=task,
            agent_name=self.card.name,
            system_prompt=DEV_SYSTEM_PROMPT,
            user_message=self.build_user_message(task, ctx),
            finish_schema=DEV_FINISH_SCHEMA,
            ctx=ctx,
        )
