from core.models import Task
from core.models import AgentRole
import uuid


def plan(goal: str) -> list[Task]:
    root_id = str(uuid.uuid4())[:8]
    tasks = []
    # 示例拆分：dev -> test -> review
    t1 = Task(task_id=f"{root_id}-dev",
              goal=f"Implement change: {goal}",
              agent_role=AgentRole.DEV)
    t2 = Task(task_id=f"{root_id}-test",
              goal=f"Generate tests for: {goal}",
              agent_role=AgentRole.TEST,
              dependencies=[t1.task_id])
    t3 = Task(task_id=f"{root_id}-review",
              goal=f"Review changes for: {goal}",
              agent_role=AgentRole.REVIEW,
              dependencies=[t2.task_id])
    return [t1, t2, t3]
