from agents.base import BaseAgent
from core.models import AgentResult, AgentRole, RiskLevel, Task, TaskStatus, AgentCard


class TestAgent(BaseAgent):

    def __init__(self, ) -> None:
        super().__init__(
            AgentCard(
                name="test_agent",
                role=AgentRole.TEST,
                capabilities=["test_generation", "test_execution_planning"],
                tools=["run_tests", "read_file"],
                risk_level=RiskLevel.MEDIUM))

    def run(self, task: Task) -> AgentResult:
        return AgentResult(agent_name=self.card.name,
                           task_id=task.task_id,
                           status=TaskStatus.SUCCESS,
                           output={
                               "message":
                               "TestAgent received task",
                               "test_plan": [
                                   "Identify affected modules",
                                   "Generate unit test cases",
                                   "Plan regression test scope",
                               ]
                           },
                           token_cost=100,
                           error=None)
