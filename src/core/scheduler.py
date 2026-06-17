import time
from typing import List, Dict, Any, Literal
from pydantic import BaseModel
from core.models import AgentResult, AgentRole, RiskLevel, Task, TaskStatus, AgentCard, StepSnapshot
from agents.dev_agent import DevAgent
from agents.base import BaseAgent


class ThinHarnessScheduler:

    agents: List[BaseAgent]
    snapshots: List[StepSnapshot]

    def __init__(self):
        self.agents = []
        self.snapshots = []

    def register_agent(self, agent: BaseAgent):
        self.agents.append(agent)

    def find_agent(self, task: Task):
        for agent in self.agents:
            if agent.can_handle(task):
                return agent
        raise ValueError(f"No agent found for role: {task.agent_role}")

    def execute_task(self, run_id, task):
        agent = self.find_agent(task)
        if (agent):
            result = agent.run(task)
            snapshot = StepSnapshot(step_id=f"{run_id}:{task.task_id}",
                                    run_id=run_id,
                                    task=task,
                                    agent_card=agent.card,
                                    result=result)
            self.snapshots.append(snapshot)
