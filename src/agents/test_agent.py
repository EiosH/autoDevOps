from agents.base import BaseAgent
from core.agent_runner import AgentRunner
from core.models import AgentCard, AgentResult, AgentRole, RiskLevel, Task, TaskStatus
from engine.llm import LLMProvider
from tools.executor import ToolExecutor

TEST_SYSTEM_PROMPT = """You are a test agent.

Use the provided tools to complete the task. The model will invoke tools natively.

Workflow:
1. read_file — read upstream dev changes and source files
2. write_patch — create or update test files
3. run_tests — execute tests (pass test_path, e.g. /tests)

If tests fail, read relevant files and fix tests or report failure clearly.
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
                name="test_agent",
                role=AgentRole.TEST,
                capabilities=["test_generation", "test_execution"],
                tools=["read_file", "write_patch", "run_tests"],
                risk_level=RiskLevel.MEDIUM,
            )
        )

    def run(self, task: Task) -> AgentResult:
        result = self.runner.run_loop(
            llm=self.llm,
            tool_executor=self.tool_executor,
            allowed_tools=self.card.tools,
            task=task,
            agent_name=self.card.name,
            system_prompt=TEST_SYSTEM_PROMPT,
            user_message=self.build_user_message(task),
            finish_schema=TEST_FINISH_SCHEMA,
        )
        if result.status == TaskStatus.SUCCESS and result.output.get("passed") is False:
            result.status = TaskStatus.FAILED
        return result
