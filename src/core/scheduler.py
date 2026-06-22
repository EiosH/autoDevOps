import json
from typing import List

from core.models import (
    Task,
    StepSnapshot,
    TaskStatus,
    ExecutionReport,
    AgentResult,
    MemoryRecord,
    MemoryType,
    RunContext,
)
from agents.base import BaseAgent


def is_snapshot_succeed(snapshot: StepSnapshot):
    return snapshot.result.status == TaskStatus.SUCCESS


class ThinHarnessScheduler:

    agents: List[BaseAgent]
    snapshots: List[StepSnapshot]
    max_retries: int

    def __init__(self, max_retries=10):
        self.agents = []
        self.snapshots = []
        self.max_retries = max_retries

    def register_agent(self, agent: BaseAgent):
        self.agents.append(agent)

    def find_agent(self, task: Task):
        for agent in self.agents:
            if agent.can_handle(task):
                return agent
        raise ValueError(f"No agent found for role: {task.agent_role}")

    def execute_task(self, run_id, task, ctx: RunContext, attempt=1):
        agent = self.find_agent(task)
        try:
            result = agent.run(task, ctx)
        except Exception as e:
            result = AgentResult(
                agent_name=agent.card.name,
                task_id=task.task_id,
                status=TaskStatus.FAILED,
                output={},
                error=str(e),
            )

        snapshot = StepSnapshot(
            step_id=f"{run_id}:{task.task_id}:{attempt}",
            run_id=run_id,
            task=task,
            agent_card=agent.card,
            result=result,
        )
        ctx.snapshots.append(snapshot)
        self.snapshots.append(snapshot)
        if result.status == TaskStatus.SUCCESS:
            self._record_episodic(ctx, snapshot)
        if result.status == TaskStatus.FAILED and attempt <= self.max_retries:
            return self.execute_task(run_id, task, ctx, attempt + 1)
        return snapshot

    def is_task_ready(self, task: Task, ctx: RunContext):
        if not task.dependencies:
            return True
        finished_success_task_ids = {
            snapshot.task.task_id
            for snapshot in ctx.snapshots
            if snapshot.result.status == TaskStatus.SUCCESS
        }
        return all(dep in finished_success_task_ids for dep in task.dependencies)

    def execute_task_graph(self, run_id, tasks: List[Task], user_goal: str = ""):
        ctx = RunContext(run_id=run_id, user_goal=user_goal)
        pending_tasks = list(tasks)
        results = []
        while pending_tasks:
            next_pending_tasks = []
            progressed = False
            for task in pending_tasks:
                if self.is_task_ready(task, ctx):
                    snapshot = self.execute_task(run_id, task, ctx)
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

    def build_report(self, run_id):
        run_snapshots = [
            snapshot for snapshot in self.snapshots if snapshot.run_id == run_id
        ]
        final_snapshots_by_task_id = {}
        for snap in run_snapshots:
            final_snapshots_by_task_id[snap.task.task_id] = snap

        final_snaps = list(final_snapshots_by_task_id.values())
        total_tasks = len(run_snapshots)
        unique_tasks = len(final_snaps)
        success_tasks = len(list(filter(is_snapshot_succeed, run_snapshots)))
        final_success_tasks = len(list(filter(is_snapshot_succeed, final_snaps)))
        failed_tasks = total_tasks - success_tasks
        final_failed_tasks = unique_tasks - final_success_tasks

        used_agent_names = set()

        return ExecutionReport(
            run_id=run_id,
            total_tasks=total_tasks,
            success_tasks=success_tasks,
            failed_tasks=failed_tasks,
            executed_task_ids=list(
                map(lambda snapshot: snapshot.task.task_id, run_snapshots)
            ),
            agent_names=[
                snap.agent_card.name
                for snap in run_snapshots
                if snap.agent_card is not None
                and not (
                    snap.agent_card.name in used_agent_names
                    or used_agent_names.add(snap.agent_card.name)
                )
            ],
            total_token_cost=sum(
                snapshot.result.token_cost for snapshot in run_snapshots
            ),
            unique_tasks=unique_tasks,
            final_success_tasks=final_success_tasks,
            final_failed_tasks=final_failed_tasks,
            retry_count=total_tasks - unique_tasks,
        )

    def _record_episodic(self, ctx: RunContext, snapshot: StepSnapshot):
        content = json.dumps(
            {
                "task_id": snapshot.task.task_id,
                "goal": snapshot.task.goal,
                "agent": snapshot.agent_card.name,
                "summary": snapshot.result.output.get("summary"),
                "output": snapshot.result.output,
            },
            ensure_ascii=False,
        )
        ctx.episodic.append(
            MemoryRecord(
                memory_id=f"{ctx.run_id}:{snapshot.task.task_id}:episodic",
                memory_type=MemoryType.EPISODIC,
                content=content,
                source="scheduler",
                metadata={
                    "task_id": snapshot.task.task_id,
                    "agent_name": snapshot.agent_card.name,
                },
            )
        )
