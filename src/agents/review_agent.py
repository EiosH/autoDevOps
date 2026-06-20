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
        goal = task.goal.lower()
        points = ["Correctness", "Maintainability"]
        if "security" in goal or "auth" in goal:
            points.append("Security")
        if "performance" in goal or "slow" in goal:
            points.append("Performance")
        if "readme" in goal or "docs" in goal:
            points.append("Documentation")

        detailed = []
        for p in points:
            if p == "Correctness":
                detailed.append("Verify logic against spec and edge cases")
            if p == "Maintainability":
                detailed.append("Check naming, modularity, and comments")
            if p == "Security":
                detailed.append("Check input validation and auth boundaries")
            if p == "Performance":
                detailed.append("Identify hot paths and expensive calls")
            if p == "Documentation":
                detailed.append("Ensure examples and usage are clear")

        return AgentResult(agent_name=self.card.name,
                           task_id=task.task_id,
                           status=TaskStatus.SUCCESS,
                           output={
                               "message": "Review points generated",
                               "review_focus": detailed
                           },
                           token_cost=30)
