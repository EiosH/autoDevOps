from agents.base import BaseAgent
from core.models import AgentResult, AgentRole, RiskLevel, Task, TaskStatus, AgentCard


class ReviewAgent(BaseAgent):

    def __init__(self, ) -> None:
        super().__init__(
            AgentCard(name="review_agent",
                      role=AgentRole.REVIEW,
                      capabilities=["code_review", "risk_analysis"],
                      tools=["read_file", "git_diff"],
                      risk_level=RiskLevel.LOW))

    def run(self, task: Task) -> AgentResult:
        return AgentResult(
            agent_name=self.card.name,
            task_id=task.task_id,
            status=TaskStatus.SUCCESS,
            output={
                "message":
                "ReviewAgent received task",
                "review_focus":
                ["Correctness", "Maintainability", "Security risks"]
            },
            token_cost=100,
            error=None)
