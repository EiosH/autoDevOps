import json
from typing import List

from core.models import (
    AgentRole,
    Task,
    StepSnapshot,
    TaskStatus,
    ExecutionReport,
    AgentResult,
    RunContext,
)
from agents.base import BaseAgent


def is_snapshot_succeed(snapshot: StepSnapshot):
    return snapshot.result.status == TaskStatus.SUCCESS


class ThinHarnessScheduler:

    agents: List[BaseAgent]
    snapshots: List[StepSnapshot]
    max_retries: int
    max_fix_cycles: int

    def __init__(self, max_retries=3, max_fix_cycles=3):
        self.agents = []
        self.snapshots = []
        self.max_retries = max_retries
        self.max_fix_cycles = max_fix_cycles

    def register_agent(self, agent: BaseAgent):
        self.agents.append(agent)

    def find_agent(self, task: Task):
        for agent in self.agents:
            if agent.can_handle(task):
                return agent
        raise ValueError(f"No agent found for role: {task.agent_role}")

    def execute_task(
        self, run_id, task, ctx: RunContext, attempt=1, auto_retry=True
    ):
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
        if (
            result.status == TaskStatus.FAILED
            and auto_retry
            and attempt < self.max_retries
        ):
            return self.execute_task(
                run_id, task, ctx, attempt + 1, auto_retry=auto_retry
            )
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

    def _latest_snapshot(
        self, ctx: RunContext, task_id: str
    ) -> StepSnapshot | None:
        matches = [s for s in ctx.snapshots if s.task.task_id == task_id]
        return matches[-1] if matches else None

    def _review_needs_fix(self, snapshot: StepSnapshot) -> bool:
        if snapshot.result.status == TaskStatus.FAILED:
            return True
        if snapshot.result.output.get("approved") is False:
            return True
        return False

    def _record_review_feedback(self, ctx: RunContext, snapshot: StepSnapshot):
        ctx.add_episodic(
            content=json.dumps(
                {
                    "type": "review_feedback",
                    "task_id": snapshot.task.task_id,
                    "approved": snapshot.result.output.get("approved"),
                    "issues": snapshot.result.output.get("issues", []),
                    "summary": snapshot.result.output.get("summary"),
                    "error": snapshot.result.error,
                },
                ensure_ascii=False,
            ),
            source="scheduler",
            memory_id=f"{ctx.run_id}:{snapshot.task.task_id}:review_feedback",
            metadata={"task_id": snapshot.task.task_id, "kind": "review_feedback"},
        )

    def _run_dag(self, run_id: str, tasks: List[Task], ctx: RunContext):
        results = []
        pending_tasks = list(tasks)
        while pending_tasks:
            next_pending_tasks = []
            progressed = False
            for task in pending_tasks:
                if self.is_task_ready(task, ctx):
                    auto_retry = task.agent_role != AgentRole.REVIEW
                    snapshot = self.execute_task(
                        run_id, task, ctx, auto_retry=auto_retry
                    )
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

    def _dev_review_fix_loop(
        self, run_id: str, tasks: List[Task], ctx: RunContext
    ):
        review_tasks = [t for t in tasks if t.agent_role == AgentRole.REVIEW]
        for review_task in review_tasks:
            dev_tasks = [
                t
                for t in tasks
                if t.task_id in review_task.dependencies
                and t.agent_role == AgentRole.DEV
            ]
            if not dev_tasks:
                continue

            for cycle in range(1, self.max_fix_cycles + 1):
                last_review = self._latest_snapshot(ctx, review_task.task_id)
                if last_review is None or not self._review_needs_fix(last_review):
                    break

                self._record_review_feedback(ctx, last_review)
                print(
                    f"\nfix cycle {cycle}/{self.max_fix_cycles}: "
                    f"review failed, re-running dev then review"
                )

                for dev_task in dev_tasks:
                    self.execute_task(
                        run_id,
                        dev_task,
                        ctx,
                        attempt=cycle + 1,
                        auto_retry=False,
                    )

                self.execute_task(
                    run_id,
                    review_task,
                    ctx,
                    attempt=cycle + 1,
                    auto_retry=False,
                )

    def execute_task_graph(self, run_id, tasks: List[Task], user_goal: str = ""):
        ctx = RunContext(run_id=run_id, user_goal=user_goal)
        results = self._run_dag(run_id, tasks, ctx)
        self._dev_review_fix_loop(run_id, tasks, ctx)
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
        ctx.add_episodic(
            content=content,
            source="scheduler",
            memory_id=f"{ctx.run_id}:{snapshot.task.task_id}:episodic",
            metadata={
                "task_id": snapshot.task.task_id,
                "agent_name": snapshot.agent_card.name,
                "kind": "step_summary",
            },
        )
