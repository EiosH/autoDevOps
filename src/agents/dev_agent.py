from agents.base import BaseAgent
from core.models import AgentResult, AgentRole, RiskLevel, Task, TaskStatus, AgentCard
from tools.executor import ToolExecutor


class DevAgent(BaseAgent):

    def __init__(self, tool_executor: ToolExecutor | None = None) -> None:
        self.tool_executor = tool_executor
        super().__init__(
            AgentCard(name="dev_agent",
                      role=AgentRole.DEV,
                      capabilities=["code_generation"],
                      tools=["read_file", "write_patch"],
                      risk_level=RiskLevel.MEDIUM))

    def run(self, task: Task) -> AgentResult:
        tool_calls = []
        if self.tool_executor and task.metadata.get("read_path"):
            call = self.tool_executor.execute(
                "read_file", path=task.metadata.get("read_path"))
            tool_calls.append(call)
        return AgentResult(agent_name=self.card.name,
                           task_id=task.task_id,
                           status=TaskStatus.SUCCESS,
                           output={
                               "message": "DevAgent received task",
                               "memories": task.metadata.get("memories", []),
                               "tool_summary":
                               [call.status for call in tool_calls]
                           },
                           token_cost=100,
                           error=None,
                           tool_calls=tool_calls)
