from typing import List
from core.models import Task, StepSnapshot, TaskStatus
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
        result = agent.run(task)
        snapshot = StepSnapshot(step_id=f"{run_id}:{task.task_id}",
                                run_id=run_id,
                                task=task,
                                agent_card=agent.card,
                                result=result)
        self.snapshots.append(snapshot)
        return snapshot

    def is_task_ready(self, task: Task):
        if not task.dependencies:
            return True
        finished_success_task_ids = {
            snapshot.task.task_id
            for snapshot in self.snapshots
            if snapshot.result.status == TaskStatus.SUCCESS
        }
        return all(dep in finished_success_task_ids
                   for dep in task.dependencies)

    def execute_tasks(self, run_id, tasks: List[Task]):
        results = []
        for task in tasks:
            if not self.is_task_ready(task):
                continue

            snapshot = self.execute_task(run_id, task)
            results.append(snapshot)
        return results

    def execute_task_graph(self, run_id, tasks: List[Task]):
        pending_tasks = list(tasks)
        results = []
        while pending_tasks:
            next_pending_tasks = []
            progressed = False
            for task in pending_tasks:
                if self.is_task_ready(task):
                    snapshot = self.execute_task(run_id, task)
                    results.append(snapshot)
                    progressed = True
                else:
                    next_pending_tasks.append(task)
            if not progressed:
                raise ValueError(
                    "Task graph cannot progress, possible cyclic or missing dependency"
                )

            pending_tasks = next_pending_tasks
        return results
