from agents.base import BaseAgent
from core.models import AgentResult, AgentRole, RiskLevel, Task, TaskStatus, AgentCard
from engine.llm import LLMProvider


class TestAgent(BaseAgent):
    llm: LLMProvider

    def __init__(
        self,
        llm: LLMProvider,
    ) -> None:
        self.llm = llm
        super().__init__(
            AgentCard(
                name="test_agent",
                role=AgentRole.TEST,
                capabilities=["test_generation", "test_execution_planning"],
                tools=["run_tests", "read_file"],
                risk_level=RiskLevel.MEDIUM))

    def run(self, task: Task) -> AgentResult:
        goal = task.goal.lower()
        affected = []
        if "readme" in goal or "文案" in goal:
            affected.append("docs/readme.md")
        if "api" in goal:
            affected.append("src/api")
        # fallback
        if not affected:
            affected = ["src/"]

        test_cases = [
            f"Unit tests for functions mentioned in goal: '{task.goal}'",
            "Edge-case tests for invalid inputs",
            "Integration tests for related modules"
        ]
        test_plan = {
            "affected_modules":
            affected,
            "test_cases_summary":
            test_cases,
            "regression_scope":
            "run existing unit + integration tests for affected modules"
        }
        return AgentResult(agent_name=self.card.name,
                           task_id=task.task_id,
                           status=TaskStatus.SUCCESS,
                           output={
                               "message": "Test plan generated",
                               "test_plan": test_plan
                           },
                           token_cost=50)
