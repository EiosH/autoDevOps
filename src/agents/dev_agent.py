from agents.base import BaseAgent
from core.models import AgentResult, AgentRole, RiskLevel, Task, TaskStatus, AgentCard


class DevAgent(BaseAgent):

    def __init__(self, ) -> None:
        super().__init__(
            AgentCard(name="dev_agent",
                      role=AgentRole.DEV,
                      capabilities=["code_generation"],
                      tools=["read_file", "write_patch"],
                      risk_level=RiskLevel.MEDIUM))

    def run(self, task: Task) -> AgentResult:
        return AgentResult(agent_name=self.card.name,
                           task_id=task.task_id,
                           status=TaskStatus.SUCCESS,
                           output={
                               "message": "DevAgent received task",
                               "memories": task.metadata.get("memories", [])
                           },
                           token_cost=100,
                           error=None)
