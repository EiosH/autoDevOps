from agents.base import BaseAgent
from core.agent_runner import AgentRunner
from core.models import AgentCard, AgentResult, AgentRole, RiskLevel, Task
from engine.llm import LLMProvider
from tools.executor import ToolExecutor

DEV_SYSTEM_PROMPT = """You are a dev agent.

Use the provided tools to complete the task. The model will invoke tools natively.

Workflow:
1. read_file — inspect existing files before editing
2. write_patch — write full file content (minimal, complete, runnable)
3. git_diff — verify changes after writing
4. shell_exec — list files only when needed

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

    def run(self, task: Task) -> AgentResult:
        return self.runner.run_loop(
            llm=self.llm,
            tool_executor=self.tool_executor,
            allowed_tools=self.card.tools,
            task=task,
            agent_name=self.card.name,
            system_prompt=DEV_SYSTEM_PROMPT,
            user_message=self.build_user_message(task),
            finish_schema=DEV_FINISH_SCHEMA,
        )
